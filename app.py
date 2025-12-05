import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# Configuração do Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///obra.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DO BANCO DE DADOS ---

class ItemSEO(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50))
    descricao = db.Column(db.String(255))
    unidade = db.Column(db.String(10))
    preco_unitario = db.Column(db.Float)
    qtd_contrato = db.Column(db.Float)

class Medicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date)
    item_id = db.Column(db.Integer, db.ForeignKey('item_seo.id'))
    qtd_executada_mes = db.Column(db.Float)
    item = db.relationship('ItemSEO', backref='medicoes')

class Financeiro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_pagamento = db.Column(db.Date)
    fornecedor = db.Column(db.String(255))
    categoria = db.Column(db.String(100))
    valor = db.Column(db.Float)

# --- ROTAS DO SITE ---

@app.route('/')
def index():
    return """
    <div style="text-align: center; margin-top: 50px; font-family: sans-serif;">
        <h1>🏗️ Sistema de Gestão de Obras</h1>
        <p>Bem-vindo ao painel de controle.</p>
        <br>
        <a href="/medicao" style="background: #0d6efd; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Ir para Medição</a>
        <br><br>
        <a href="/upload" style="color: #666;">📂 Configuração e Upload de Dados</a>
    </div>
    """

@app.route('/medicao')
def tela_medicao():
    itens = ItemSEO.query.all()
    lista_para_tela = []
    for item in itens:
        total_executado = sum([m.qtd_executada_mes for m in item.medicoes])
        lista_para_tela.append({
            'id': item.id,
            'descricao': item.descricao,
            'unidade': item.unidade,
            'contrato': item.qtd_contrato,
            'acumulado': total_executado
        })
    return render_template('medicao.html', itens=lista_para_tela)

@app.route('/upload', methods=['GET', 'POST'])
def upload_arquivos():
    if request.method == 'POST':
        # 1. Processar Arquivo SEO (Orçamento)
        arquivo_seo = request.files.get('arquivo_seo')
        if arquivo_seo:
            # Limpa o banco antigo para não duplicar
            ItemSEO.query.delete()
            try:
                # CORREÇÃO AQUI: Adicionado encoding='latin1' para ler acentos do Excel
                df = pd.read_csv(arquivo_seo, sep=None, engine='python', encoding='latin1')
                
                # Procura as colunas certas
                for _, row in df.iterrows():
                    if pd.isna(row.get('Descrição')) or row.get('Descrição') == 'Descrição':
                        continue
                        
                    novo_item = ItemSEO(
                        codigo=str(row.get('Código', '')),
                        descricao=str(row.get('Descrição', 'Sem Nome')),
                        unidade=str(row.get('Unid.', 'un')),
                        preco_unitario=float(str(row.get('Unit.', 0)).replace('R$', '').replace('.', '').replace(',', '.') or 0),
                        qtd_contrato=float(str(row.get('Quant.', 0)).replace('.', '').replace(',', '.') or 0)
                    )
                    db.session.add(novo_item)
            except Exception as e:
                return f"Erro ao ler SEO: {str(e)}"

        # 2. Processar Arquivo GERFIN (Financeiro)
        arquivo_gerfin = request.files.get('arquivo_gerfin')
        if arquivo_gerfin:
            Financeiro.query.delete()
            try:
                # CORREÇÃO AQUI: Adicionado encoding='latin1' também
                df_fin = pd.read_csv(arquivo_gerfin, sep=None, engine='python', encoding='latin1')
                
                for _, row in df_fin.iterrows():
                    if pd.isna(row.get('Valor adotado GERFIN')): continue
                    
                    novo_fin = Financeiro(
                        fornecedor=str(row.get('Nome', 'Fornecedor')),
                        categoria=str(row.get('Categoria', 'Geral')),
                        valor=float(str(row.get('Valor adotado GERFIN', 0)).replace('.', '').replace(',', '.') or 0),
                        data_pagamento=pd.to_datetime(row.get('Data de pagamento'), dayfirst=True, errors='coerce')
                    )
                    db.session.add(novo_fin)
            except Exception as e:
                return f"Erro ao ler GERFIN: {str(e)}"

        db.session.commit()
        return "<h1>Dados Importados com Sucesso!</h1><a href='/medicao'>Ver Tabela</a>"

    # HTML da página de upload (O resto continua igual)
    return """
    <div style="font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; border: 1px solid #ccc; border-radius: 10px;">
        <h2>📂 Importação de Dados</h2>
        <p>Selecione seus arquivos CSV para preencher o sistema.</p>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 20px;">
                <label><strong>1. Arquivo SEO (Orçamento):</strong></label><br>
                <input type="file" name="arquivo_seo" accept=".csv">
            </div>
            <div style="margin-bottom: 20px;">
                <label><strong>2. Arquivo GERFIN (Financeiro):</strong></label><br>
                <input type="file" name="arquivo_gerfin" accept=".csv">
            </div>
            <button type="submit" style="background: #198754; color: white; padding: 10px 20px; border: none; cursor: pointer; font-size: 16px;">
                🚀 Enviar e Processar
            </button>
        </form>
    </div>
    """

# Cria o banco ao iniciar
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
