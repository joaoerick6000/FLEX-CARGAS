import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma_chave_muito_secreta'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração do banco de dados (ajustado para funcionar localmente e no Render)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///cargas.db'

db = SQLAlchemy(app)

# --- Modelos do Banco de Dados ---


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(100), nullable=True)


class Nota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(20), nullable=False)  # 'avista' ou 'anotacao'
    lancamentos = db.relationship(
        'Lancamento', backref='nota', lazy=True, cascade="all, delete-orphan")
    cliente = db.relationship('Cliente', backref='notas')


class Lancamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey('nota.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey(
        'produto.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)

    produto = db.relationship('Produto', backref='lancamentos')


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), nullable=False)
    acao = db.Column(db.String(255), nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)

# --- Funções Auxiliares ---


def get_dashboard_data():
    total_clientes = Cliente.query.count()
    total_produtos = Produto.query.count()
    total_notas = Nota.query.count()
    total_volumes = db.session.query(
        db.func.sum(Lancamento.quantidade)).scalar() or 0
    return {
        'total_clientes': total_clientes,
        'total_produtos': total_produtos,
        'total_notas': total_notas,
        'total_volumes': total_volumes
    }


def log_acao(usuario, acao):
    new_log = Log(usuario=usuario, acao=acao)
    db.session.add(new_log)
    db.session.commit()

# --- Rotas da Aplicação ---


@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            log_acao(session['username'], f'Login bem-sucedido.')
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha inválidos.', 'danger')
        log_acao('Desconhecido',
                 f'Tentativa de login falha com o usuário: {username}.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    log_acao(session.get('username'), f'Logout realizado.')
    session.pop('username', None)
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Usuário já existe. Escolha outro nome.', 'danger')
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            log_acao(username, f'Novo usuário cadastrado.')
            flash('Usuário cadastrado com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
    return render_template('cadastro.html')


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    data = get_dashboard_data()
    return render_template('dashboard.html', data=data)

# --- Rotas de Clientes ---


@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        nome = request.form.get('nome')
        telefone = request.form.get('telefone')
        email = request.form.get('email')
        new_cliente = Cliente(nome=nome, telefone=telefone, email=email)
        db.session.add(new_cliente)
        db.session.commit()
        log_acao(session['username'], f'Cliente "{nome}" cadastrado.')
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))

    lista_clientes = Cliente.query.all()
    return render_template('clientes.html', clientes=lista_clientes)


@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nome = request.form.get('nome')
        cliente.telefone = request.form.get('telefone')
        cliente.email = request.form.get('email')
        db.session.commit()
        log_acao(session['username'], f'Cliente "{cliente.nome}" editado.')
        flash('Cliente editado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    return render_template('editar_cliente.html', cliente=cliente)


@app.route('/clientes/excluir/<int:id>', methods=['POST'])
def excluir_cliente(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    cliente = Cliente.query.get_or_404(id)
    nome_cliente = cliente.nome

    # Verifica se existem notas vinculadas
    if Nota.query.filter_by(cliente_id=id).first():
        flash('Não é possível excluir o cliente. Existem notas vinculadas.', 'danger')
        return redirect(url_for('clientes'))

    db.session.delete(cliente)
    db.session.commit()
    log_acao(session['username'], f'Cliente "{nome_cliente}" excluído.')
    flash('Cliente excluído com sucesso!', 'success')
    return redirect(url_for('clientes'))

# --- Rotas de Produtos ---


@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        nome = request.form.get('nome')
        codigo = request.form.get('codigo')
        categoria = request.form.get('categoria')
        new_produto = Produto(nome=nome, codigo=codigo, categoria=categoria)
        db.session.add(new_produto)
        db.session.commit()
        log_acao(session['username'], f'Produto "{nome}" cadastrado.')
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('produtos'))

    lista_produtos = Produto.query.all()
    return render_template('produtos.html', produtos=lista_produtos)


@app.route('/produtos/editar/<int:id>', methods=['GET', 'POST'])
def editar_produto(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        produto.nome = request.form.get('nome')
        produto.codigo = request.form.get('codigo')
        produto.categoria = request.form.get('categoria')
        db.session.commit()
        log_acao(session['username'], f'Produto "{produto.nome}" editado.')
        flash('Produto editado com sucesso!', 'success')
        return redirect(url_for('produtos'))
    return render_template('editar_produto.html', produto=produto)


@app.route('/produtos/excluir/<int:id>', methods=['POST'])
def excluir_produto(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    produto = Produto.query.get_or_404(id)
    nome_produto = produto.nome

    # Verifica se existem lançamentos vinculados
    if Lancamento.query.filter_by(produto_id=id).first():
        flash('Não é possível excluir o produto. Existem lançamentos vinculados.', 'danger')
        return redirect(url_for('produtos'))

    db.session.delete(produto)
    db.session.commit()
    log_acao(session['username'], f'Produto "{nome_produto}" excluído.')
    flash('Produto excluído com sucesso!', 'success')
    return redirect(url_for('produtos'))

# --- Rotas de Lançamentos (PDV) ---


@app.route('/lancamentos', methods=['GET'])
def lancamentos():
    if 'username' not in session:
        return redirect(url_for('login'))

    clientes = Cliente.query.all()

    if 'carrinho' not in session:
        session['carrinho'] = []

    return render_template('lancamentos.html', clientes=clientes)


@app.route('/add_to_carrinho', methods=['POST'])
def add_to_carrinho():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado.'})

    data = request.json
    produto_id = data.get('produto_id')
    quantidade = data.get('quantidade')

    if not all([produto_id, quantidade]):
        return jsonify({'success': False, 'message': 'Dados incompletos.'})

    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({'success': False, 'message': 'Produto não encontrado.'})

    if 'carrinho' not in session:
        session['carrinho'] = []

    # Verifica se o produto já está no carrinho
    item_existente = next(
        (item for item in session['carrinho'] if item['produto_id'] == int(produto_id)), None)
    if item_existente:
        item_existente['quantidade'] += int(quantidade)
    else:
        session['carrinho'].append({
            'produto_id': produto.id,
            'produto_nome': produto.nome,
            'quantidade': int(quantidade),
        })
    session.modified = True

    return jsonify({'success': True, 'message': 'Item adicionado.', 'carrinho': session['carrinho']})


@app.route('/get_carrinho')
def get_carrinho():
    return jsonify(session.get('carrinho', []))


@app.route('/clear_carrinho')
def clear_carrinho():
    session.pop('carrinho', None)
    session.modified = True
    return jsonify({'success': True})


@app.route('/modificar_carrinho', methods=['POST'])
def modificar_carrinho():
    data = request.json
    produto_id = data.get('produto_id')
    nova_quantidade = data.get('quantidade')

    carrinho = session.get('carrinho', [])
    for item in carrinho:
        if item['produto_id'] == produto_id:
            item['quantidade'] = nova_quantidade
            if item['quantidade'] <= 0:
                carrinho.remove(item)
            break
    session['carrinho'] = carrinho
    session.modified = True
    return jsonify({'success': True, 'carrinho': session['carrinho']})


@app.route('/buscar_produto/<query>')
def buscar_produto(query):
    produtos = Produto.query.filter(
        (Produto.nome.ilike(f'%{query}%')) | (
            Produto.codigo.ilike(f'%{query}%'))
    ).all()

    results = [{'id': p.id, 'nome': p.nome, 'codigo': p.codigo}
               for p in produtos]
    return jsonify(results)


@app.route('/finalizar_carga', methods=['POST'])
def finalizar_carga():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado.'})

    data = request.json
    cliente_id = data.get('cliente_id')
    tipo_finalizacao = data.get('tipo')
    carrinho = session.get('carrinho', [])

    if not carrinho:
        return jsonify({'success': False, 'message': 'Carrinho vazio. Adicione itens antes de finalizar.'})

    if tipo_finalizacao == 'anotacao' and not cliente_id:
        return jsonify({'success': False, 'message': 'Selecione um cliente para finalizar com anotação.'})

    new_nota = Nota(cliente_id=cliente_id, tipo=tipo_finalizacao)
    db.session.add(new_nota)
    db.session.commit()  # Salva a nota para ter um ID

    for item in carrinho:
        new_lancamento = Lancamento(
            nota_id=new_nota.id,
            produto_id=item['produto_id'],
            quantidade=item['quantidade']
        )
        db.session.add(new_lancamento)

    db.session.commit()
    log_acao(session['username'],
             f'Nota #{new_nota.id} finalizada como "{tipo_finalizacao}".')
    session.pop('carrinho', None)
    session.modified = True

    return jsonify({'success': True, 'redirect_url': url_for('historico')})

# --- Rotas de Histórico e Notas ---


@app.route('/historico')
def historico():
    if 'username' not in session:
        return redirect(url_for('login'))

    todas_notas = Nota.query.order_by(Nota.data.desc()).all()
    return render_template('historico.html', notas=todas_notas)


@app.route('/nota/<int:nota_id>')
def ver_nota(nota_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    nota = Nota.query.get_or_404(nota_id)
    lancamentos = Lancamento.query.filter_by(nota_id=nota.id).all()
    clientes = Cliente.query.all()
    return render_template('ver_nota.html', nota=nota, lancamentos=lancamentos, clientes=clientes)


@app.route('/nota/editar/<int:nota_id>', methods=['POST'])
def editar_nota(nota_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    nota = Nota.query.get_or_404(nota_id)

    # Atualiza o cliente se for uma anotação
    if nota.tipo == 'anotacao':
        novo_cliente_id = request.form.get('cliente_id')
        if novo_cliente_id:
            nota.cliente_id = novo_cliente_id
            log_acao(
                session['username'], f'Cliente da nota #{nota_id} alterado para o cliente ID {novo_cliente_id}.')

    # Lógica de edição de itens da nota
    for key, value in request.form.items():
        if key.startswith('qtd_'):
            lancamento_id = key.split('_')[1]
            lancamento = Lancamento.query.get(lancamento_id)
            nova_qtd = int(value)

            if nova_qtd <= 0:
                log_acao(
                    session['username'], f'Item (ID {lancamento_id}) da nota #{nota_id} removido.')
                db.session.delete(lancamento)
            else:
                lancamento.quantidade = nova_qtd
                log_acao(
                    session['username'], f'Item (ID {lancamento_id}) da nota #{nota_id} modificado para Qtd {nova_qtd}.')

    # Adicionar novos itens
    novos_produtos_ids = request.form.getlist('novo_produto_id')
    novas_quantidades = request.form.getlist('nova_quantidade')
    for prod_id, qtd in zip(novos_produtos_ids, novas_quantidades):
        if prod_id and qtd and int(qtd) > 0:
            new_lancamento = Lancamento(
                nota_id=nota.id,
                produto_id=int(prod_id),
                quantidade=int(qtd)
            )
            db.session.add(new_lancamento)
            log_acao(
                session['username'], f'Novo item (Produto ID {prod_id}) adicionado à nota #{nota_id}.')

    db.session.commit()
    flash('Nota atualizada com sucesso!', 'success')
    return redirect(url_for('ver_nota', nota_id=nota.id))


@app.route('/nota/excluir/<int:nota_id>', methods=['POST'])
def excluir_nota(nota_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    nota = Nota.query.get_or_404(nota_id)
    db.session.delete(nota)
    db.session.commit()
    log_acao(session['username'], f'Nota #{nota_id} excluída.')
    flash('Nota excluída com sucesso!', 'success')
    return redirect(url_for('historico'))


@app.route('/conta_cliente/<int:cliente_id>')
def conta_cliente(cliente_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    cliente = Cliente.query.get_or_404(cliente_id)
    notas = Nota.query.filter_by(
        cliente_id=cliente_id, tipo='anotacao').order_by(Nota.data.desc()).all()

    return render_template('conta_cliente.html', cliente=cliente, notas=notas)


# Cria tabelas e um usuário admin se não existir
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed_password = generate_password_hash('admin123')
        new_user = User(username='admin', password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

# Bloco para rodar localmente (opcional)
if __name__ == '__main__':
    app.run(debug=True)