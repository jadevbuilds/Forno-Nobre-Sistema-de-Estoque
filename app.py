# Importações principais do sistema
import os  # Manipulação de arquivos e diretórios
from datetime import timedelta, datetime  # Trabalhar com datas e tempo
from flask import Flask, render_template, request, redirect, url_for, session, flash  # Funções do Flask
from flask_sqlalchemy import SQLAlchemy  # ORM para banco de dados
from werkzeug.utils import secure_filename  # Segurança no upload de arquivos
from sqlalchemy import or_, func  # Funções avançadas de consulta SQL

# Define o diretório base do projeto
basedir = os.path.abspath(os.path.dirname(__file__))

# Criação da aplicação Flask
app = Flask(__name__)

# Configuração do banco SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'padaria_db.db')

# Chave secreta para sessões (login)
app.config['SECRET_KEY'] = 'chave_secreta_padaria'

# Pasta onde as imagens serão salvas
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')

# Sessão não permanente (expira)
app.config['SESSION_PERMANENT'] = False

# Tempo de duração da sessão (30 minutos)
app.permanent_session_lifetime = timedelta(minutes=30)

# Inicializa o banco de dados
db = SQLAlchemy(app)

# ================================
# MODELOS (TABELAS DO BANCO)
# ================================

# Tabela de insumos (estoque)
class Insumo(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # ID único
    nome = db.Column(db.String(100))  # Nome do item
    quantidade_atual = db.Column(db.Float, default=0.0)  # Quantidade atual
    quantidade_minima = db.Column(db.Float, default=0.0)  # Quantidade mínima
    unidade = db.Column(db.String(20))  # Unidade (kg, un, lt)
    categoria = db.Column(db.String(50))  # Categoria do item


# Tabela de usuários
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)  # Nome único
    email = db.Column(db.String(100), unique=True)  # Email único
    senha = db.Column(db.String(50))  # Senha (ATENÇÃO: sem criptografia)
    nivel = db.Column(db.String(20))  # admin ou func
    cpf = db.Column(db.String(14))  # CPF
    telefone = db.Column(db.String(15))  # Telefone
    foto = db.Column(db.String(200), default='default.png')  # Foto de perfil
    data_nascimento = db.Column(db.String(10))  # Data de nascimento
    ultimo_acesso = db.Column(db.DateTime)  # Último login


# Tabela de solicitações de alteração de perfil
class Solicitacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)  # FK usuário
    nome_novo = db.Column(db.String(100))
    email_novo = db.Column(db.String(100))
    telefone_novo = db.Column(db.String(20))
    status = db.Column(db.String(20), default='pendente')  # pendente/aprovado/recusado
    
    # Relacionamento com usuário
    usuario = db.relationship('Usuario', backref='solicitacoes')
    
    foto_nova = db.Column(db.String(200))  # Nova foto enviada


# Tabela de histórico de ações
class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)  # Data da ação
    usuario_nome = db.Column(db.String(100))  # Nome do usuário
    produto_nome = db.Column(db.String(100))  # Produto alterado
    tipo = db.Column(db.String(20))  # entrada, saída, cadastro, exclusão
    quantidade = db.Column(db.Float)  # Quantidade movimentada
    unidade = db.Column(db.String(10))  # Unidade
    saldo_final = db.Column(db.Float)  # Saldo após operação
    observacao = db.Column(db.String(200))  # Observação
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))  # FK usuário

    # Propriedade para buscar o usuário completo
    @property
    def usuario_completo(self):
        return Usuario.query.get(self.usuario_id) if self.usuario_id else Usuario.query.filter_by(username=self.usuario_nome).first()


# ================================
# ROTA DE LOGIN
# ================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Recebe dados do formulário
        login_input = request.form['username'].strip()
        senha_input = request.form['senha']

        # Remove caracteres não numéricos do CPF
        login_numeros = ''.join(filter(str.isdigit, login_input))
        
        # Busca usuário por:
        # username OU CPF (formatado ou sem máscara)
        user = Usuario.query.filter(
            or_(
                func.lower(func.trim(Usuario.username)) == func.lower(login_input),
                Usuario.cpf == login_input,
                func.replace(func.replace(Usuario.cpf, '.', ''), '-', '') == login_numeros
            ),
            Usuario.senha == senha_input
        ).first()

        if user:
            # Atualiza último acesso
            user.ultimo_acesso = datetime.now()
            db.session.commit()

            # Cria sessão
            session['user_id'] = user.id
            session['user_nome'] = user.username

            return redirect(url_for('index'))
        
        # Mensagem de erro
        flash('⚠️ Usuário/CPF ou senha inválidos!', 'danger')

    return render_template('login.html')


# ================================
# REGISTRO DE USUÁRIO
# ================================
@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        # Coleta dados do formulário
        username = request.form['username']
        email = request.form['email']
        cpf = request.form['cpf']
        telefone = request.form['telefone']
        senha = request.form['senha']
        data_nascimento = request.form['data_nascimento']
        nivel = request.form.get('nivel', 'func')

        # Verifica duplicidade
        usuario_existente = Usuario.query.filter(
            (Usuario.username == username) |
            (Usuario.cpf == cpf) |
            (Usuario.email == email)
        ).first()

        if usuario_existente:
            flash('⚠️ Usuário, CPF ou E-mail já cadastrado!', 'danger')
            return redirect(url_for('registrar'))

        # Cria novo usuário
        novo_usuario = Usuario(
            username=username,
            email=email,
            cpf=cpf,
            telefone=telefone,
            senha=senha,
            data_nascimento=data_nascimento,
            nivel=nivel,
            foto='default.png'
        )

        db.session.add(novo_usuario)
        db.session.commit()

        flash('✅ Novo usuário cadastrado!', 'success')
        return redirect(url_for('login'))

    return render_template('registrar.html')


# ================================
# TELA PRINCIPAL (ESTOQUE)
# ================================
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = Usuario.query.get(session['user_id'])
    insumos = Insumo.query.all()

    # Lista de alertas (abaixo do mínimo)
    alertas = [i for i in insumos if (i.quantidade_atual or 0) < (i.quantidade_minima or 0)]

    return render_template('index.html', insumos=insumos, usuario=user, alertas=alertas)


# ================================
# ADICIONAR INSUMO
# ================================
@app.route('/adicionar_insumo', methods=['POST'])
def adicionar_insumo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Dados do formulário
    nome = request.form.get('nome')
    categoria = request.form.get('categoria')
    unidade = request.form.get('unidade')

    # Conversão de número (aceita vírgula)
    qtd_str = request.form.get('quantidade').replace(',', '.')
    qtd = float(qtd_str)
    minimo = float(request.form.get('minimo'))

    user = Usuario.query.get(session['user_id'])

    # Verifica duplicidade
    if Insumo.query.filter_by(nome=nome).first():
        flash("⚠️ Este insumo já está cadastrado!", "warning")
        return redirect(url_for('index'))

    try:
        # Cria insumo
        novo_insumo = Insumo(
            nome=nome,
            categoria=categoria,
            unidade=unidade,
            quantidade_atual=qtd,
            quantidade_minima=minimo
        )
        db.session.add(novo_insumo)

        # Registra histórico
        db.session.add(Historico(
            produto_nome=nome,
            quantidade=qtd,
            unidade=unidade,
            tipo='cadastro',
            usuario_nome=user.username,
            usuario_id=user.id,
            saldo_final=qtd,
            observacao="Cadastro inicial"
        ))

        db.session.commit()
        flash(f"✅ {nome} cadastrado com sucesso!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erro ao cadastrar: {str(e)}", "danger")

    return redirect(url_for('index'))


# ================================
# EXCLUIR INSUMO
# ================================
@app.route('/excluir_insumo/<int:id>', methods=['GET', 'POST'])
def excluir_insumo(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    item = Insumo.query.get_or_404(id)
    nome_removido = item.nome

    db.session.delete(item)
    db.session.commit()

    flash(f"🗑️ {nome_removido} removido do estoque.", "info")
    return redirect(url_for('index'))


# ================================
# MOVIMENTAÇÃO DE ESTOQUE
# ================================
@app.route('/movimentar/<int:id>', methods=['POST'])
def movimentar(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    item = Insumo.query.get(id)
    qtd = float(request.form.get('quantidade'))
    tipo = request.form.get('tipo')
    user = Usuario.query.get(session['user_id'])

    # Entrada ou saída
    if tipo == 'entrada':
        item.quantidade_atual += qtd
    else:
        item.quantidade_atual -= qtd

    # Registro no histórico
    log = Historico(
        produto_nome=item.nome,
        quantidade=qtd,
        unidade=item.unidade,
        tipo=tipo,
        usuario_nome=user.username,
        usuario_id=user.id,
        saldo_final=item.quantidade_atual,
        observacao=request.form.get('motivo')
    )

    db.session.add(log)
    db.session.commit()

    flash(f"📦 Movimentação de {item.nome} registrada!", "success")
    return redirect(url_for('index'))


# ================================
# PERFIL
# ================================
@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    usuario = Usuario.query.get(session['user_id'])

    if request.method == 'POST':
        if usuario.nivel == 'admin':
            # Atualização direta
            usuario.username = request.form.get('username')
            usuario.email = request.form.get('email')
            usuario.telefone = request.form.get('telefone')
            usuario.data_nascimento = request.form.get('data_nascimento')

            # Upload de foto
            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    filename = secure_filename(f"user_{usuario.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    usuario.foto = filename

            # Atualiza nome no histórico
            Historico.query.filter_by(usuario_id=usuario.id).update({Historico.usuario_nome: usuario.username})

            session['user_nome'] = usuario.username
            db.session.commit()

            flash('✅ Perfil atualizado!', 'success')

        else:
            # Cria solicitação
            foto_filename = None

            if 'foto' in request.files:
                file = request.files['foto']
                if file.filename != '':
                    foto_filename = secure_filename(f"req_{usuario.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_filename))

            sol = Solicitacao(
                usuario_id=usuario.id,
                nome_novo=request.form.get('username'),
                email_novo=request.form.get('email'),
                telefone_novo=request.form.get('telefone'),
                foto_nova=foto_filename
            )

            db.session.add(sol)
            db.session.commit()

            flash('📩 Solicitação enviada!', 'success')

        return redirect(url_for('perfil'))

    solicitacoes = Solicitacao.query.filter_by(status='pendente').all() if usuario.nivel == 'admin' else []

    return render_template('perfil.html', usuario=usuario, solicitacoes=solicitacoes)


# ================================
# PROCESSAR SOLICITAÇÕES
# ================================
@app.route('/processar_solicitacao/<int:id>/<string:acao>')
def processar_solicitacao(id, acao):
    sol = Solicitacao.query.get(id)

    if acao == 'aprovar':
        user = Usuario.query.get(sol.usuario_id)

        # Atualiza dados
        user.username = sol.nome_novo
        user.email = sol.email_novo
        user.telefone = sol.telefone_novo

        if sol.foto_nova:
            user.foto = sol.foto_nova

        # Atualiza histórico
        Historico.query.filter_by(usuario_id=user.id).update({Historico.usuario_nome: user.username})

        sol.status = 'aprovado'
        flash('✅ Solicitação aprovada!', 'success')

    else:
        sol.status = 'recusado'
        flash('❌ Solicitação recusada.', 'success')

    db.session.commit()
    return redirect(url_for('perfil'))


# ================================
# HISTÓRICO
# ================================
@app.route('/historico')
def historico():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = Usuario.query.get(session['user_id'])

    # Ordena do mais recente para o mais antigo
    logs = Historico.query.order_by(Historico.data.desc()).all()

    return render_template('historico.html', logs=logs, usuario=user)


# ================================
# LOGOUT
# ================================
@app.route('/logout')
def logout():
    session.clear()  # Limpa sessão
    return redirect(url_for('login'))


# ================================
# CONTEXTO GLOBAL (BADGE DE NOTIFICAÇÃO)
# ================================
@app.context_processor
def inject_pendentes():
    if 'user_id' in session:
        user = Usuario.query.get(session['user_id'])

        if user and user.nivel == 'admin':
            contagem = Solicitacao.query.filter_by(status='pendente').count()
            return dict(contagem_pendentes=contagem)

    return dict(contagem_pendentes=0)


# ================================
# INICIALIZAÇÃO DO SISTEMA
# ================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Cria tabelas

        # Corrige valores nulos
        insumos_com_erro = Insumo.query.filter(
            (Insumo.quantidade_atual == None) |
            (Insumo.quantidade_minima == None)
        ).all()

        for i in insumos_com_erro:
            if i.quantidade_atual is None:
                i.quantidade_atual = 0.0
            if i.quantidade_minima is None:
                i.quantidade_minima = 0.0

        # Cria admin padrão se não existir
        if not Usuario.query.filter_by(username='Joao Admin').first():
            db.session.add(Usuario(
                username='Joao Admin',
                senha='123',
                nivel='admin',
                cpf='140.883.084-17',
                email='admin@fornonobre.com'
            ))

        db.session.commit()
        print("✅ Banco de Dados OK!")

    # Inicia servidor Flask
    app.run(debug=True)