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
        <a href="/upload" style="background: #6610f2;">📂 Configuração e Upload de Dados</a>
        <br><br>
        <a href="/dashboard" style="background: #6610f2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">📊 Ver Dashboard</a>
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
    
    # Função auxiliar para limpar números (R$, pontos, vírgulas)
    def limpar_moeda(valor):
        if pd.isna(valor): return 0.0
        s = str(valor).replace('R$', '').strip()
        if not s: return 0.0
        # Se tiver vírgula, assume formato BR (1.000,00)
        if ',' in s:
            s = s.replace('.', '')  # Remove ponto de milhar
            s = s.replace(',', '.') # Troca vírgula por ponto decimal
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
                # Lê o arquivo "cru", sem cabeçalho, para não se perder
                df = pd.read_csv(arquivo_seo, sep=None, engine='python', encoding='latin1', header=None)
                
                # Procura a linha onde começa a tabela (procura a palavra "Item" na primeira coluna)
                linha_inicio = -1
                for i, row in df.iterrows():
                    primeira_celula = str(row[0]).strip()
                    if 'Item' in primeira_celula:
                        linha_inicio = i
                        break
                
                if linha_inicio != -1:
                    # Começa a ler 2 linhas DEPOIS do cabeçalho (pula a linha de Unid/Quant que fica embaixo)
                    for i in range(linha_inicio + 2, len(df)):
                        row = df.iloc[i]
                        
                        # Mapeamento fixo das colunas (Baseado na sua planilha)
                        # Col 0: Item (1.1.1) | Col 2: Código | Col 3: Descrição | Col 4: Unid 
                        # Col 5: Quantidade | Col 6: Preço Unitário
                        
                        desc = str(row[3])
                        
                        # Pula linhas vazias ou linhas de totais
                        if pd.isna(desc) or desc == 'nan' or desc.strip() == '':
                            continue

                        # Tenta pegar o preço. Se não tiver preço, assume 0 (pode ser título de seção)
                        preco = limpar_moeda(row[6])
                        quant = limpar_moeda(row[5])
                        
                        novo_item = ItemSEO(
                            codigo=str(row[2]), # Coluna C (Código)
                            descricao=desc,     # Coluna D (Descrição)
                            unidade=str(row[4]), # Coluna E (Unidade)
                            preco_unitario=preco, # Coluna G (Unitário - verifique se na sua é G mesmo)
                            qtd_contrato=quant    # Coluna F (Quantidade)
                        )
                        db.session.add(novo_item)
                else:
                    return "Erro: Não encontrei a coluna 'Item' na planilha SEO."
                    
            except Exception as e:
                return f"Erro ao ler SEO: {str(e)}"

        # 2. Processar Arquivo GERFIN (Financeiro)
        arquivo_gerfin = request.files.get('arquivo_gerfin')
        if arquivo_gerfin:
            Financeiro.query.delete()
            try:
                # Mantém a leitura por nome para o GERFIN, que parece estar correto
                df_fin = pd.read_csv(arquivo_gerfin, sep=None, engine='python', encoding='latin1')
                for _, row in df_fin.iterrows():
                    val = row.get('Valor adotado GERFIN')
                    if pd.isna(val): continue
                    
                    val_limpo = limpar_moeda(val)
                    if val_limpo == 0: continue # Pula valores zerados

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
        return "<h1>Dados Importados com Sucesso!</h1><p>Agora a tabela deve estar completa.</p><a href='/medicao'>Ver Medição</a>"

    # HTML (Igual ao anterior)
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
@app.route('/dashboard')
def dashboard():
    # 1. Busca dados brutos do banco
    # Pega medições e multiplica pelo preço unitário do item (Valor Agregado)
    medicoes = db.session.query(
        Medicao.data_referencia, 
        db.func.sum(Medicao.qtd_executada_mes * ItemSEO.preco_unitario)
    ).join(ItemSEO).group_by(Medicao.data_referencia).all()

    # Pega gastos do financeiro agrupado por data
    gastos = db.session.query(
        Financeiro.data_pagamento, 
        db.func.sum(Financeiro.valor)
    ).group_by(Financeiro.data_pagamento).all()

    # 2. Organiza em Dataframes (Tabelas Virtuais) para facilitar a soma por mês
    df_prod = pd.DataFrame(medicoes, columns=['Data', 'Valor']) if medicoes else pd.DataFrame(columns=['Data', 'Valor'])
    df_gasto = pd.DataFrame(gastos, columns=['Data', 'Valor']) if gastos else pd.DataFrame(columns=['Data', 'Valor'])

    # Garante que as datas são datas mesmo
    if not df_prod.empty: df_prod['Data'] = pd.to_datetime(df_prod['Data'])
    if not df_gasto.empty: df_gasto['Data'] = pd.to_datetime(df_gasto['Data'])

    # Agrupa tudo por Mês (Ano-Mês) para alinhar os dois gráficos
    # Ex: Tudo de 01/08 a 31/08 vira "2025-08"
    df_prod['Mes'] = df_prod['Data'].dt.to_period('M').astype(str) if not df_prod.empty else []
    df_gasto['Mes'] = df_gasto['Data'].dt.to_period('M').astype(str) if not df_gasto.empty else []

    # Cria uma lista única de meses que existem no sistema
    todos_meses = sorted(list(set(df_prod['Mes'].unique().tolist() + df_gasto['Mes'].unique().tolist())))

    # Listas finais para o gráfico
    lista_prod_mes = []
    lista_gasto_mes = []
    
    prod_acumulado = 0
    gasto_acumulado = 0
    lista_prod_acum = []
    lista_gasto_acum = []

    for mes in todos_meses:
        # Soma do Mês
        v_prod = df_prod[df_prod['Mes'] == mes]['Valor'].sum()
        v_gasto = df_gasto[df_gasto['Mes'] == mes]['Valor'].sum() # GERFIN já vem negativo? Se sim, multiplicar por -1
        
        # Ajuste: Se no seu CSV o gasto é negativo, remova o abs(). Se for positivo, deixe como está.
        # Assumindo que gasto entra como positivo para comparar no gráfico:
        v_gasto = abs(v_gasto) 

        lista_prod_mes.append(v_prod)
        lista_gasto_mes.append(v_gasto)

        # Soma Acumulada
        prod_acumulado += v_prod
        gasto_acumulado += v_gasto
        lista_prod_acum.append(prod_acumulado)
        lista_gasto_acum.append(gasto_acumulado)

    # Totais para os Cards
    total_prod = f"{prod_acumulado:,.2f}"
    total_gasto = f"{gasto_acumulado:,.2f}"
    saldo_final = f"{(prod_acumulado - gasto_acumulado):,.2f}"

    return render_template('dashboard.html', 
                           labels=todos_meses,
                           prod_mes=lista_prod_mes,
                           gasto_mes=lista_gasto_mes,
                           prod_acum=lista_prod_acum,
                           gasto_acum=lista_gasto_acum,
                           total_produzido=total_prod,
                           total_gasto=total_gasto,
                           saldo=saldo_final)
if __name__ == '__main__':
    app.run(debug=True)
