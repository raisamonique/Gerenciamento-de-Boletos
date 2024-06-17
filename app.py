from flask import Flask, render_template, request, redirect, url_for
from flask_uploads import UploadSet, configure_uploads, DOCUMENTS
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from datetime import datetime, timedelta
import pandas as pd
import sqlite3
import os
import re
import shutil
import logging

# Configure o logging
logging.basicConfig(filename='boletos_log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['UPLOADED_DOCUMENTS_DEST'] = 'C:/Users/F0994560/site_boleto/uploads'
documents = UploadSet('documents', DOCUMENTS)
configure_uploads(app, documents)

# Criar a base de dados e a tabela
def create_database():
    conn = sqlite3.connect('boletos_base.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boletos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_externo TEXT UNIQUE,  
            nome VARCHAR(100),
            cpf TEXT,
            data_emissao DATE,
            data_registro DATE,
            data_vencimento DATE,
            valor REAL,
            cod_linha_digitavel TEXT,
            link_boleto TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Verificação se na base de dados já existe, caso não criar
create_database()

# Função para fazer backup do banco de dados
def backup_database():
    backup_file = 'boletos_base_backup.db'
    shutil.copyfile('boletos_base.db', backup_file)
    logging.info(f"Backup do banco de dados criado como '{backup_file}'")  

# Função para limpar o banco de dados
def clean_database():
    conn = sqlite3.connect('boletos_base.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM boletos')
    conn.commit()
    conn.close()
    logging.info("Banco de dados limpo!")

# Função de backup a cada 90 dias
last_backup = datetime.now() - timedelta(days=90)
if (datetime.now() - last_backup).days >= 90:
    backup_database()
    clean_database()
    last_backup = datetime.now()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'arquivo' in request.files:
        arquivo = request.files['arquivo']
        if arquivo.filename != '':
            filename = secure_filename(arquivo.filename)
            file_path = os.path.join(app.config['UPLOADED_DOCUMENTS_DEST'], filename)
            arquivo.save(file_path)

            if filename.endswith('.xlsx'):
                try:
                    # Carregar dados da planilha 
                    print(f"Caminho do arquivo: {file_path}") 
                    df = pd.read_excel(file_path, 
                                      names=['id_externo', 'nome', 'cpf', 'data_emissao', 'data_vencimento', 
                                             'data_registro', 'valor', 'cod_linha_digitavel', 'link_boleto'],
                                      dtype={'id_externo': str, 'nome': str, 'cpf': str, 'data_emissao': 'datetime64[ns]',
                                             'data_vencimento': 'datetime64[ns]', 'data_registro': 'datetime64[ns]',
                                             'cod_linha_digitavel': str, 'link_boleto': str},
                                      converters={'valor': lambda x: float(x.replace('R$ ', '').replace(',', '.'))}, 
                                      date_format='%d/%m/%Y',  # importante Formato de data dia/mes/ano
                                     )
                    print(df.info()) #importante internamente verificação se o DataFrame está sendo criado
                    print(df.head())  #importante internamente verificaçãoVerifique os dados lidos

                    # Forçar conversão para string na planilha
                    df['id_externo'] = df['id_externo'].astype(str) 

                    # Contadores do rel.
                    linhas_total = len(df)
                    linhas_importadas = 0
                    linhas_nao_importadas = 0
                    erros = []  # Lista para armazenar no rel.

                    # Salvando inf no bd
                    conn = sqlite3.connect('boletos_base.db')
                    cursor = conn.cursor()
                    for index, row in df.iterrows():
                        try:
                            # Validação dos dados e formatação das  datas e outros componentes string  
                            id_externo = str(row['id_externo'])  
                            if not id_externo.isdigit() or len(id_externo) != 8:
                                erros.append(f"Linha {index + 2}: ID Externo inválido. Deve ser um número de 8 dígitos.")
                                linhas_nao_importadas += 1
                                continue  

                            if not isinstance(row['nome'], str) or len(row['nome'].strip()) == 0:
                                erros.append(f"Linha {index + 2}: Nome inválido. Deve ser uma string não vazia.")
                                linhas_nao_importadas += 1
                                continue  

                            if not isinstance(row['cpf'], str) or not row['cpf'].isdigit() or len(row['cpf']) != 11:
                                erros.append(f"Linha {index + 2}: CPF inválido. Deve ser um número de 11 dígitos.")
                                linhas_nao_importadas += 1
                                continue  

                            if not isinstance(row['cod_linha_digitavel'], str) or len(row['cod_linha_digitavel']) != 54:
                                erros.append(f"Linha {index + 2}: Código da Linha Digitável inválido. Deve ter 54 caracteres.")
                                linhas_nao_importadas += 1
                                continue  

                            data_emissao = row['data_emissao'].strftime('%Y-%m-%d') 
                            data_registro = row['data_registro'].strftime('%Y-%m-%d') 
                            data_vencimento = row['data_vencimento'].strftime('%Y-%m-%d') 

                            # Inserção do boleto no bd
                            cursor.execute('''
                                INSERT INTO boletos (id_externo, nome, cpf, data_emissao, data_registro, data_vencimento, valor, cod_linha_digitavel, link_boleto)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                id_externo,  
                                row['nome'],
                                row['cpf'],  
                                data_emissao,
                                data_registro,
                                data_vencimento,
                                row['valor'],
                                row['cod_linha_digitavel'],
                                row['link_boleto']
                            ))
                            linhas_importadas += 1
                        except sqlite3.IntegrityError as e:
                            # Tratamento erro de violação de chave UNIQUE
                            erros.append(
                                f"Linha {index + 2}: Erro ao importar: {e}. CPF ou ID Externo já existe no banco de dados.")
                            linhas_nao_importadas += 1
                        except Exception as e:
                            # Captura de outros erros
                            erros.append(f"Linha {index + 2}: Erro ao importar: {e}")
                            linhas_nao_importadas += 1

                    # Fechamento da conexão com bd
                    conn.commit()
                    conn.close()

                    # Verificaçãodas linhas
                    if linhas_importadas == linhas_total:
                        message = "Sua planilha foi importada com sucesso!"
                        return render_template('relatorio.html', message=message,
                                               linhas_total=linhas_total,
                                               linhas_importadas=linhas_importadas,
                                               linhas_nao_importadas=linhas_nao_importadas,
                                               erros=erros)
                    else:
                        return render_template('relatorio.html',
                                               linhas_total=linhas_total,
                                               linhas_importadas=linhas_importadas,
                                               linhas_nao_importadas=linhas_nao_importadas,
                                               erros=erros)
                except Exception as e:
                    return f'Erro ao carregar o arquivo: {e}'
            else:
                return 'Formato de arquivo inválido. Por favor, utilize arquivos .xlsx'
    return 'Erro ao carregar o arquivo.'

@app.route('/relatorio')# Rota HTML rel.
def relatorio():
    return render_template('relatorio.html')

@app.route('/aluno')# Rota HTML aluno.
def aluno():
    return render_template('aluno.html')

@app.route('/consultar_boletos', methods=['POST'])# Rota HTML consulta_boletos
def consultar_boletos():
    if request.method == 'POST':
        cpf = request.form['cpf']
        conn = sqlite3.connect('boletos_base.db')
        cursor = conn.cursor()
        # Calcula a data limite de 20 dias atrás teste 
        data_limite = datetime.now() - timedelta(days=20)
    
        cursor.execute('''
            SELECT * FROM boletos 
            WHERE cpf = ? 
            AND data_vencimento >= ? 
        ''', (cpf, data_limite.strftime('%Y-%m-%d')))  # Filtra por data de vencimento
        boletos = cursor.fetchall()

        if boletos:
            formatted_boletos = [
                {
                    "cod_linha_digitavel": boleto[8],
                    "cpf": boleto[3],
                    "data_emissao": datetime.strptime(boleto[4], '%Y-%m-%d').strftime('%d/%m/%Y'),
                    "data_registro": datetime.strptime(boleto[5], '%Y-%m-%d').strftime('%d/%m/%Y'),
                    "data_vencimento": datetime.strptime(boleto[6], '%Y-%m-%d').strftime('%d/%m/%Y'),
                    "id": boleto[0],
                    "id_externo": boleto[1],
                    "link_boleto": boleto[9],
                    "nome": boleto[2],
                    "valor": boleto[7]
                }
                for boleto in boletos
            ]
            return render_template('boletos.html', cpf=cpf, boletos=formatted_boletos)
        else:
            return render_template('boletos.html', cpf=cpf, message="Nenhum boleto encontrado para este CPF.")

        conn.close()
if __name__ == '__main__':
    app.run(debug=True)
