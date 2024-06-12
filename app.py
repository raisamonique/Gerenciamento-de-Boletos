from flask import Flask, render_template, request, redirect, url_for
from flask_uploads import UploadSet, configure_uploads, DOCUMENTS
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import pandas as pd
import sqlite3
import os
import re

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
            cpf TEXT UNIQUE,
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

# Verificar se a base de dados já existe, senão cria
create_database()


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
                    # Carregar dados da planilha (especificar tipos de dados das colunas de data)
                    print(f"Caminho do arquivo: {file_path}") # Verifique o caminho
                    df = pd.read_excel(file_path, 
                                      names=['id_externo', 'nome', 'cpf', 'data_emissao', 'data_vencimento', 
                                             'data_registro', 'valor', 'cod_linha_digitavel', 'link_boleto'],
                                      dtype={'id_externo': str, 'nome': str, 'cpf': str, 'data_emissao': 'datetime64[ns]',
                                             'data_vencimento': 'datetime64[ns]', 'data_registro': 'datetime64[ns]',
                                             'cod_linha_digitavel': str, 'link_boleto': str},
                                      converters={'valor': lambda x: float(x.replace('R$ ', '').replace(',', '.'))}, 
                                      date_format='%d/%m/%Y',  # Formato de data dia/mes/ano
                                     )
                    print(df.info()) # Verifique se o DataFrame está sendo criado
                    print(df.head())  # Verifique os dados lidos

                    # Forçar conversão para string após ler a planilha
                    df['id_externo'] = df['id_externo'].astype(str) 

                    # Contadores para o relatório
                    linhas_total = len(df)
                    linhas_importadas = 0
                    linhas_nao_importadas = 0
                    erros = []  # Lista para armazenar os erros

                    # Salvar informações no banco de dados
                    conn = sqlite3.connect('boletos_base.db')
                    cursor = conn.cursor()
                    for index, row in df.iterrows():
                        try:
                            # Validar dados e formatar as datas (já são datas no Pandas, então apenas converte para string)
                            id_externo = str(row['id_externo'])  # Forçando a conversão para string
                            if not id_externo.isdigit() or len(id_externo) != 8:
                                erros.append(f"Linha {index + 2}: ID Externo inválido. Deve ser um número de 8 dígitos.")
                                linhas_nao_importadas += 1
                                continue  # Pula para a próxima linha

                            if not isinstance(row['nome'], str) or len(row['nome'].strip()) == 0:
                                erros.append(f"Linha {index + 2}: Nome inválido. Deve ser uma string não vazia.")
                                linhas_nao_importadas += 1
                                continue  # Pula para a próxima linha

                            if not isinstance(row['cpf'], str) or not row['cpf'].isdigit() or len(row['cpf']) != 11:
                                erros.append(f"Linha {index + 2}: CPF inválido. Deve ser um número de 11 dígitos.")
                                linhas_nao_importadas += 1
                                continue  # Pula para a próxima linha

                            if not isinstance(row['cod_linha_digitavel'], str) or len(row['cod_linha_digitavel']) != 54:
                                erros.append(f"Linha {index + 2}: Código da Linha Digitável inválido. Deve ter 54 caracteres.")
                                linhas_nao_importadas += 1
                                continue  # Pula para a próxima linha

                            data_emissao = row['data_emissao'].strftime('%Y-%m-%d') 
                            data_registro = row['data_registro'].strftime('%Y-%m-%d') 
                            data_vencimento = row['data_vencimento'].strftime('%Y-%m-%d') 

                            # Inserir o boleto no banco de dados
                            cursor.execute('''
                                INSERT INTO boletos (id_externo, nome, cpf, data_emissao, data_registro, data_vencimento, valor, cod_linha_digitavel, link_boleto)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                id_externo,  # id_externo agora é uma string
                                row['nome'],
                                row['cpf'],  # Deixe o CPF como string
                                data_emissao,
                                data_registro,
                                data_vencimento,
                                row['valor'],
                                row['cod_linha_digitavel'],
                                row['link_boleto']
                            ))
                            linhas_importadas += 1
                        except sqlite3.IntegrityError as e:
                            # Tratar erro de violação de chave UNIQUE
                            erros.append(
                                f"Linha {index + 2}: Erro ao importar: {e}. CPF ou ID Externo já existe no banco de dados.")
                            linhas_nao_importadas += 1
                        except Exception as e:
                            # Captura outros tipos de erro
                            erros.append(f"Linha {index + 2}: Erro ao importar: {e}")
                            linhas_nao_importadas += 1

                    # Fechar a conexão com o banco de dados
                    conn.commit()
                    conn.close()

                    # Verifique se todas as linhas foram importadas com sucesso
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

@app.route('/relatorio')
def relatorio():
    return render_template('relatorio.html')

@app.route('/aluno')
def aluno():
    return render_template('aluno.html')

@app.route('/consultar_boletos', methods=['POST'])
def consultar_boletos():
    if request.method == 'POST':
        cpf = request.form['cpf']
        conn = sqlite3.connect('boletos_base.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM boletos WHERE cpf = ?', (cpf,))
        boletos = cursor.fetchall()

        if boletos:
            formatted_boletos = [
                {
                    "cod_linha_digitavel": boleto[3],
                    "cpf": boleto[1],
                    "data_emissao": boleto[6],
                    "data_registro": boleto[7],
                    "data_vencimento": boleto[5],
                    "id": boleto[0],
                    "id_externo": boleto[8],
                    "link_boleto": boleto[9],
                    "nome": boleto[2],
                    "valor": boleto[4]
                }
                for boleto in boletos
            ]
            return render_template('boletos.html', cpf=cpf, boletos=formatted_boletos)
        else:
            return render_template('boletos.html', cpf=cpf, message="Nenhum boleto encontrado para este CPF.")

        conn.close()
if __name__ == '__main__':
    app.run(debug=True)
