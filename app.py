from flask import Flask, render_template, request, redirect, url_for
from flask_uploads import UploadSet, configure_uploads, DOCUMENTS
from werkzeug.utils import secure_filename
import pandas as pd
import sqlite3

app = Flask(__name__)
app.config['UPLOADED_DOCUMENTS_DEST'] = 'uploads'
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
                    # Carregamendo dos dados da planilha
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
                    for index, row in df.iterrows():
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
                    conn.commit()
                    conn.close()

                    return 'Arquivo carregado com sucesso!'
                except Exception as e:
                    return f'Erro ao carregar o arquivo: {e}'
            else:
                return 'Formato de arquivo inválido. Por favor, utilize arquivos .xlsx'
    return 'Erro ao carregar o arquivo.'

if __name__ == '__main__':
    app.run(debug=True)
