import os
from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# Configuração do Banco de Dados (Pega a senha da nuvem ou usa local para teste)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///obra.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DO BANCO DE DADOS (Tabelas) ---

class ItemSEO(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50))
    descricao = db.Column(db.String(255))
    unidade = db.Column(db.String(10))
    qtd_contrato = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)

class Medicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date) # Ex: 01/08/2025
    item_id = db.Column(db.Integer, db.ForeignKey('item_seo.id'))
    qtd_executada_mes = db.Column(db.Float)
    
    # Relacionamento para facilitar consultas
    item = db.relationship('ItemSEO', backref='medicoes')

# --- ROTAS DO SITE (Páginas) ---

@app.route('/')
def index():
    # Página inicial (Dashboard)
    return "<h1>Sistema de Gestão de Obras</h1><a href='/medicao'>Ir para Medição</a>"

@app.route('/medicao', methods=['GET'])
def tela_medicao():
    # Busca todos os itens do contrato
    itens = ItemSEO.query.all()
    
    lista_para_tela = []
    
    # Para cada item, calcula o acumulado até hoje
    for item in itens:
        total_executado = sum([m.qtd_executada_mes for m in item.medicoes])
        
        lista_para_tela.append({
            'id': item.id,
            'descricao': item.descricao,
            'unidade': item.unidade,
            'contrato': item.qtd_contrato,
            'acumulado': total_executado
        })
    
    # Renderiza o HTML (aquele que desenhamos antes) passando os dados do banco
    return render_template('medicao.html', itens=lista_para_tela)

@app.route('/salvar_medicao', methods=['POST'])
def salvar():
    data_hoje = datetime.today().date()
    
    # Pega os dados enviados pelo formulário HTML
    formulario = request.form
    
    for key, valor in formulario.items():
        if key.startswith("qtd_mes_") and valor:
            # Extrai o ID do item do nome do campo (ex: qtd_mes_12)
            item_id = int(key.split('_')[2])
            qtd = float(valor)
            
            if qtd > 0:
                nova_medicao = Medicao(
                    data_referencia=data_hoje,
                    item_id=item_id,
                    qtd_executada_mes=qtd
                )
                db.session.add(nova_medicao)
    
    db.session.commit()
    return "<h1>Medição Salva com Sucesso!</h1><a href='/medicao'>Voltar</a>"

# Cria o banco de dados se não existir (apenas na primeira vez)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
