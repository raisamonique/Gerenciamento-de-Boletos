from flask import Flask, render_template, request, redirect, url_for
from flask_uploads import UploadSet, configure_uploads, DOCUMENTS
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import pandas as pd
import sqlite3
import os

app = Flask(__name__)
app.config['UPLOADED_DOCUMENTS_DEST'] = 'C:\\Users\\F0994560\\site_boleto\\uploads'
documents = UploadSet('documents', DOCUMENTS)
configure_uploads(app, documents)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'arquivo' in request.files:
        arquivo = request.files['arquivo']
        if arquivo.filename != '':
            filename = secure_filename(arquivo.filename)
            arquivo.save(os.path.join(app.config['UPLOADED_DOCUMENTS_DEST'], filename))

            if filename.endswith('.xlsx'):
                try:
                    # Carregamento dos dados da planilha
                    df = pd.read_excel(os.path.join(app.config['UPLOADED_DOCUMENTS_DEST'], filename))

                    # Validação dos dados 
                    for index, row in df.iterrows():
                        if not isinstance(row['nome'], str) or len(row['nome'].strip()) == 0:
                            return 'Nome inválido. Por favor, verifique a coluna "Nome" na planilha.'
                        if not isinstance(row['cpf'], str) or not all(c.isdigit() for c in row['cpf']):
                            return 'CPF inválido. Por favor, verifique a coluna "CPF" na planilha.'
                        

                    # Salvando inf no bd 
                    conn = sqlite3.connect('boletos.db')
                    cursor = conn.cursor()
                    linhas_importadas = 0
                    linhas_nao_importadas = 0
                    linhas_atualizadas = 0
                    linhas_nao_atualizadas = 0
                    linhas_repetidas = 0

                    for index, row in df.iterrows():
                        # Verificação se o boleto já existe no bd
                        cursor.execute('''
                            SELECT * FROM boletos WHERE cpf = ? AND cod_linha_digitavel = ?
                        ''', (row['cpf'], row['cod_linha_digitavel']))
                        boleto_existente = cursor.fetchone()

                        if boleto_existente:
                            # Boleto já existe
                            linhas_repetidas += 1
                        else:
                            # Inserir o boleto no bd
                            try:
                                cursor.execute('''
                                    INSERT INTO boletos (nome, cpf, data_emissao, data_registro, data_vencimento, valor, cod_linha_digitavel, link_boleto)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    row['nome'],
                                    row['cpf'],
                                    row['data_emissao'],
                                    row['data_registro'],
                                    row['data_vencimento'],
                                    row['valor'],
                                    row['cod_linha_digitavel'],
                                    row['link_boleto']
                                ))
                                linhas_importadas += 1
                            except Exception as e:
                                linhas_nao_importadas += 1
                                print(f"Erro ao inserir boleto: {e}")

                    conn.commit()
                    conn.close()

                    # Criar resultados
                    resultados = {
                        'total_linhas': len(df),
                        'linhas_importadas': linhas_importadas,
                        'linhas_nao_importadas': linhas_nao_importadas,
                        'linhas_atualizadas': linhas_atualizadas,
                        'linhas_nao_atualizadas': linhas_nao_atualizadas,
                        'linhas_repetidas': linhas_repetidas
                    }

                    return render_template('resultados.html', resultados=resultados)
                except Exception as e:
                    return f'Erro ao carregar o arquivo: {e}'
            else:
                return 'Formato de arquivo inválido. Por favor, utilize arquivos .xlsx'
    return 'Erro ao carregar o arquivo.'

if __name__ == '__main__':
    app.run(debug=True)
