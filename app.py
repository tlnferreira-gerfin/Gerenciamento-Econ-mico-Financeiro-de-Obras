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
    # Função auxiliar para limpar dinheiro (R$, espaços, pontos e vírgulas)
    def limpar_moeda(valor):
        if pd.isna(valor): return 0.0
        
        # Converte para texto e remove R$ e espaços vazios
        s = str(valor).replace('R$', '').strip()
        
        # Se estiver vazio após limpar, retorna 0
        if not s: return 0.0
        
        # Lógica para números brasileiros (Ex: 1.250,50 ou 830,00)
        # Se tiver vírgula, assumimos que é decimal
        if ',' in s:
            s = s.replace('.', '')  # Remove ponto de milhar (1.250 -> 1250)
            s = s.replace(',', '.') # Troca vírgula por ponto (1250,50 -> 1250.50)
        
        try:
            return float(s)
        except ValueError:
            return 0.0

    if request.method == 'POST':
        # 1. Processar Arquivo SEO (Orçamento)
        arquivo_seo = request.files.get('arquivo_seo')
        if arquivo_seo:
            ItemSEO.query.delete()
            try:
                df = pd.read_csv(arquivo_seo, sep=None, engine='python', encoding='latin1')
                for _, row in df.iterrows():
                    desc = str(row.get('Descrição', ''))
                    if pd.isna(desc) or desc.strip() == 'Descrição' or desc.strip() == '':
                        continue
                        
                    novo_item = ItemSEO(
                        codigo=str(row.get('Código', '')),
                        descricao=desc,
                        unidade=str(row.get('Unid.', 'un')),
                        # Usa a nova função de limpeza aqui
                        preco_unitario=limpar_moeda(row.get('Unit.', 0)),
                        qtd_contrato=limpar_moeda(row.get('Quant.', 0))
                    )
                    db.session.add(novo_item)
            except Exception as e:
                return f"Erro ao ler SEO: {str(e)}"

        # 2. Processar Arquivo GERFIN (Financeiro)
        arquivo_gerfin = request.files.get('arquivo_gerfin')
        if arquivo_gerfin:
            Financeiro.query.delete()
            try:
                df_fin = pd.read_csv(arquivo_gerfin, sep=None, engine='python', encoding='latin1')
                for _, row in df_fin.iterrows():
                    # Pula linha se não tiver valor
                    raw_val = row.get('Valor adotado GERFIN')
                    if pd.isna(raw_val): continue
                    
                    val_limpo = limpar_moeda(raw_val)
                    if val_limpo == 0: continue

                    novo_fin = Financeiro(
                        fornecedor=str(row.get('Nome', 'Fornecedor')),
                        categoria=str(row.get('Categoria', 'Geral')),
                        valor=val_limpo,
                        data_pagamento=pd.to_datetime(row.get('Data de pagamento'), dayfirst=True, errors='coerce')
                    )
                    db.session.add(novo_fin)
            except Exception as e:
                return f"Erro ao ler GERFIN: {str(e)}"

        db.session.commit()
        return "<h1>Dados Importados com Sucesso!</h1><a href='/medicao'>Ver Tabela</a>"

    # HTML da página de upload
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
@app.route('/salvar_medicao', methods=['POST'])
def salvar_medicao():
    # 1. Pega a data de hoje (ou poderia ser um campo de data na tela)
    data_hoje = datetime.today().date()
    
    # 2. Varre todos os campos que vieram do formulário
    formulario = request.form
    itens_salvos = 0
    
    for key, valor in formulario.items():
        # Procura campos que começam com 'item_' (ex: item_12)
        if key.startswith("item_") and valor:
            try:
                # O nome do campo é 'item_ID_mes'. Vamos pegar só o ID.
                # Ex: 'item_15_mes' -> splita em ['item', '15', 'mes'] -> pega o '15'
                parts = key.split('_')
                if len(parts) >= 2:
                    item_id = int(parts[1])
                    qtd_digitada = float(str(valor).replace('.', '').replace(',', '.'))
                    
                    if qtd_digitada != 0:
                        nova_medicao = Medicao(
                            data_referencia=data_hoje,
                            item_id=item_id,
                            qtd_executada_mes=qtd_digitada
                        )
                        db.session.add(nova_medicao)
                        itens_salvos += 1
            except ValueError:
                continue # Ignora se digitou algo que não é numero
    
    db.session.commit()
    return f"<h1>Sucesso!</h1><p>{itens_salvos} itens foram medidos e salvos.</p><a href='/medicao'>Voltar</a>"
if __name__ == '__main__':
    app.run(debug=True)
