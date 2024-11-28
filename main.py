from flask import Flask, render_template, request, redirect, flash, url_for, session
import fdb
import smtplib
import re
from email.mime.text import MIMEText

# Chave secreta
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'

# Conectar com o banco de dados
host = 'localhost'
database = r'C:\Users\Aluno\Downloads\coisafinanca\FINANCA.FDB'
user = 'sysdba'
password = 'sysdba'


con = fdb.connect(host=host, database=database, user=user, password=password)

def email_adicionar_receita(con, session):

    email = session['email']
    id_usuario = session['id_usuario']

    if not email or not id_usuario:
        raise ValueError("Informações de sessão inválidas. Certifique-se de que 'email' e 'id_usuario' estão definidos.")

    cursor = con.cursor()
    cursor.execute(
        'SELECT FIRST 1 VALOR, DATADIA, FONTE FROM RECEITAS WHERE ID_USUARIO = ? ORDER BY ID_RECEITA DESC',
        (id_usuario,))
    receita = cursor.fetchone()

    if not receita:
        raise ValueError("Nenhuma receita encontrada para o usuário especificado.")

    valor = receita[0]
    datadia = receita[1]
    fonte = receita[2]

    subject = "Receita adicionada"
    body = (
        f"A receita no valor de R${valor} da fonte {fonte} no dia {datadia} "
        f"foi adicionada em sua conta."
    )

    sender = "senseofspending@gmail.com"
    recipients = [email]  # Lista de destinatários
    password = "dyhvmufjdyngqsno"  # Substitua pela sua senha de aplicativo

    # Enviar o e-mail
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(sender, password)
            smtp_server.sendmail(sender, recipients, msg.as_string())
            print("Mensagem enviada com sucesso!")

    except Exception as e:
        raise RuntimeError(f"Erro ao enviar o e-mail: {e}")


def validar_senha(senha):
    padrao = r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
    return bool(re.fullmatch(padrao, senha))


# Carregar página de criar conta
@app.route('/criar_conta')
def criar_conta():
    return render_template('criar_conta.html')


# Criar conta
@app.route('/cadastro', methods=['POST'])
def cadastro():
    nome = request.form['nome']
    email = request.form['email']
    senha = request.form['senha']

    # Validação da senha
    if not validar_senha(senha):
        flash(
            "A senha deve ter pelo menos 8 caracteres, incluindo letras maiúsculas, minúsculas, números e caracteres especiais.",
            "error")
        return redirect(url_for('criar_conta'))

    # Criando o cursor
    cursor = con.cursor()

    try:
        # Verificar se o usuario já existe com a combinação de fonte e data
        cursor.execute("SELECT 1 FROM usuario WHERE EMAIL = ?", (email,))
        if cursor.fetchone():  # Se existir algum registro
            flash("Conta já cadastrada!", "error")
            return redirect(url_for('criar_conta'))

        # Inserir o novo registro
        cursor.execute("INSERT INTO usuario (NOME, EMAIL, SENHA) VALUES (?, ?, ?)",
                       (nome, email, senha))
        con.commit()
        flash("Usuário criado com sucesso!", "success")
    except Exception as e:
        # Se ocorrer um erro, exibe uma mensagem de erro
        flash(f"Erro ao cadastrar usuário: {str(e)}", "error")
        con.rollback()  # Faz rollback caso ocorra erro
    finally:
        cursor.close()

    return redirect(url_for('login'))


class Receitas:
    def __init__(self, id_receita, valor, datadia, fonte, id_usuario):
        self.id_receita = id_receita
        self.valor = valor
        self.datadia = datadia
        self.fonte = fonte
        self.id_usuario = id_usuario


# Carregar página da tabelas de receitas
@app.route('/tabela_receitas')
def tabela_receitas():
    if 'id_usuario' not in session: # verifica se existe um usario na sessão
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))

    id_usuario = session['id_usuario']
    cursor = con.cursor()
    cursor.execute('SELECT id_receita, valor, datadia, fonte FROM receitas WHERE id_usuario = ?', (id_usuario,))
    receitas = cursor.fetchall()
    cursor.close()
    return render_template('tabela_receitas.html', receitas=receitas)


# Carregar página de criar receitas
@app.route('/receitas')
def receitas():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    return render_template('receitas.html', titulo='Nova Receita')


#Criar receita
@app.route('/criar_receita', methods=['POST'])
def criar_receita():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))

    valor = request.form['valor']
    datadia = request.form['datadia']
    fonte = request.form.get('fonte').upper()
    id_usuario = session['id_usuario']

    cursor = con.cursor()
    try:
        # Verificar se a receita já existe para o mesmo usuário
        cursor.execute("SELECT 1 FROM receitas WHERE FONTE = ? AND DATADIA = ? AND ID_USUARIO = ?",
                       (fonte, datadia, id_usuario))
        if cursor.fetchone():
            flash("Erro: Receita já cadastrada.", "error")
            return redirect(url_for('receitas'))

        # Inserir o novo registro
        cursor.execute("INSERT INTO receitas (VALOR, DATADIA, FONTE, ID_USUARIO) VALUES (?, ?, ?, ?)",
                       (valor, datadia, fonte, id_usuario))
        con.commit()
        flash("Receita cadastrada com sucesso!", "success")

        # Enviar e-mail após criação da receita
        try:
            email_adicionar_receita(con, session)
        except Exception as email_error:
            flash(f"Erro ao enviar o e-mail: {str(email_error)}", "error")

    except Exception as e:
        flash(f"Erro ao cadastrar receita: {str(e)}", "error")
        con.rollback()
    finally:
        cursor.close()

    return redirect(url_for('tabela_receitas'))


# Carregar página de receitas
@app.route('/atualizar_receita')
def atuaizar_receita():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    return render_template('editar_receita.html', titulo='Editar Receita')


# Editar receita
@app.route('/editar_receita/<int:id>', methods=['GET', 'POST'])
def editar_receita(id):
    cursor = con.cursor()  # Abre o cursor

    # Buscar o  específico para edição
    cursor.execute("SELECT ID_RECEITA, VALOR, DATADIA, FONTE FROM receitas WHERE ID_RECEITA = ?", (id,))
    receita = cursor.fetchone()

    if not receita:
        cursor.close()  # Fecha o cursor se o  não for encontrado
        flash("Receita não encontrado!", "error")
        return redirect(url_for('tabela_receitas'))  # Redireciona para a página principal se o  não for encontrado

    if request.method == 'POST':
        # Coleta os dados do formulário
        valor = request.form['valor']
        datadia = request.form['datadia']
        fonte = request.form['fonte']

        # Atualiza o  no banco de dados
        cursor.execute("UPDATE receitas SET VALOR = ?,  DATADIA = ?, FONTE = ? WHERE ID_RECEITA = ?",
                       (valor, datadia, fonte, id))
        con.commit()  # Salva as mudanças no banco de dados
        cursor.close()  # Fecha o cursor
        flash("Receita atualizada com sucesso!", "success")
        return redirect(url_for('tabela_receitas'))  # Redireciona para a página principal após a atualização

    cursor.close()  # Fecha o cursor ao final da função, se não for uma requisição POST
    return render_template('editar_receita.html', receita=receita, titulo='Editar Receita')


# Deletar receitas
@app.route('/deletar_receita/<int:id>', methods=('POST',))
def deletar_receita(id):
    cursor = con.cursor()  # Abre o cursor

    try:
        cursor.execute('DELETE FROM receitas WHERE id_receita = ?', (id,))
        con.commit()  # Salva as alterações no banco de dados
        flash('Receita excluída com sucesso!', 'success')  # Mensagem de sucesso
    except Exception as e:
        con.rollback()  # Reverte as alterações em caso de erro
        flash('Erro ao excluir a receita.', 'error')  # Mensagem de erro
    finally:
        cursor.close()  # Fecha o cursor independentemente do resultado

    return redirect(url_for('tabela_receitas'))  # Redireciona para a página principal


class Despesas:
    def __init__(self, id_despesas, valor, datadia, fonte, id_usuario):
        self.id_despesas = id_despesas
        self.valor = valor
        self.datadia = datadia
        self.fonte = fonte
        self.id_usuario = id_usuario


# Carregar página da tabela de despesas
@app.route('/tabela_despesas')
def tabela_despesas():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))

    id_usuario = session['id_usuario']
    cursor = con.cursor()
    cursor.execute('SELECT id_despesas, valor, datadia, fonte FROM despesas WHERE id_usuario = ?', (id_usuario,))
    despesas = cursor.fetchall()
    cursor.close()
    return render_template('tabela_despesas.html', despesas=despesas)


# Carregar página para criar despesas
@app.route('/despesas')
def despesas():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    return render_template('despesas.html', titulo='Nova Despesa')


# Criar despesas
@app.route('/criar_despesa', methods=['POST'])
def criar_despesa():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))

    valor = request.form['valor']
    datadia = request.form['datadia']
    fonte = request.form.get('fonte').upper()
    id_usuario = session['id_usuario']

    cursor = con.cursor()
    try:
        # Verificar se a despesa já existe para o mesmo usuário
        cursor.execute("SELECT 1 FROM despesas WHERE FONTE = ? AND DATADIA = ? AND ID_USUARIO = ?",
                       (fonte, datadia, id_usuario))
        if cursor.fetchone():
            flash("Erro: Despesa já cadastrada.", "error")
            return redirect(url_for('despesas'))

        # Inserir o novo registro
        cursor.execute("INSERT INTO despesas (VALOR, DATADIA, FONTE, ID_USUARIO) VALUES (?, ?, ?, ?)",
                       (valor, datadia, fonte, id_usuario))
        con.commit()
        flash("Despesa cadastrada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao cadastrar despesa: {str(e)}", "error")
        con.rollback()
    finally:
        cursor.close()

    return redirect(url_for('tabela_despesas'))


# Carregar página para editar despesas
@app.route('/atualizar_despesa')
def atuaizar_despesa():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    return render_template('editar_despesa.html', titulo='Editar Despesa')


# Editar despesas
@app.route('/editar_despesa/<int:id>', methods=['GET', 'POST'])
def editar_despesa(id):
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    cursor = con.cursor()  # Abre o cursor

    # Buscar o  específico para edição
    cursor.execute("SELECT ID_DESPESAS, VALOR, DATADIA, FONTE FROM despesas WHERE ID_DESPESAS = ?", (id,))
    despesa = cursor.fetchone()

    if not despesa:
        cursor.close()  # Fecha o cursor se o  não for encontrado
        flash("Despesa não encontrada!", "error")
        return redirect(url_for('tabela_despesas'))  # Redireciona para a página principal se o  não for encontrado

    if request.method == 'POST':
        # Coleta os dados do formulário
        valor = request.form['valor']
        datadia = request.form['datadia']
        fonte = request.form.get('fonte').upper()

        # Atualiza o  no banco de dados
        cursor.execute("UPDATE despesas SET VALOR = ?, DATADIA = ?, FONTE = ? WHERE ID_DESPESAS = ?",
                       (valor, datadia, fonte, id))
        con.commit()  # Salva as mudanças no banco de dados
        cursor.close()  # Fecha o cursor
        flash("Despesa atualizada com sucesso!", "success")
        return redirect(url_for('tabela_despesas'))  # Redireciona para a página principal após a atualização

    cursor.close()  # Fecha o cursor ao final da função, se não for uma requisição POST
    return render_template('editar_despesa.html', despesa=despesa, titulo='Editar Despesa')


# Deletar despesas
@app.route('/deletar_despesa/<int:id>', methods=('POST',))
def deletar_despesa(id):
    cursor = con.cursor()  # Abre o cursor

    try:
        cursor.execute('DELETE FROM despesas WHERE id_despesas = ?', (id,))
        con.commit()  # Salva as alterações no banco de dados
        flash('Despesa excluída com sucesso!', 'success')  # Mensagem de sucesso
    except Exception as e:
        con.rollback()  # Reverte as alterações em caso de erro
        flash('Erro ao excluir a despesa.', 'error')  # Mensagem de erro
    finally:
        cursor.close()  # Fecha o cursor independentemente do resultado

    return redirect(url_for('tabela_despesas'))  # Redireciona para a página principal

#Rota da Calculadora
@app.route('/controle')
def controle():
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))

    id_usuario = session['id_usuario']
    cursor = con.cursor()
    total_receita = 0
    total_despesa = 0
    try:
        # Somar receitas
        cursor.execute("SELECT COALESCE(VALOR, 0) FROM receitas WHERE id_usuario = ?", (id_usuario,))
        for valor in cursor.fetchall():
            total_receita += valor[0]

        # Somar despesas
        cursor.execute("SELECT COALESCE(VALOR, 0) FROM despesas WHERE id_usuario = ?", (id_usuario,))
        for valor in cursor.fetchall():
            total_despesa += valor[0]

        # Calcular saldo
        total_perda_lucro = total_receita - total_despesa

    except Exception as e:
        print(f"Erro ao calcular valores: {e}")
        flash("Erro ao carregar os dados financeiros.")
        total_receita = total_despesa = total_perda_lucro = 0

    finally:
        cursor.close()

    # Formatando os valores para exibição
    total_receita = f"{total_receita:.2f}"
    total_despesa = f"{total_despesa:.2f}"
    total_perda_lucro = f"{total_perda_lucro:.2f}"

    print(f"Total Receita: {total_receita}, Total Despesa: {total_despesa}, Saldo: {total_perda_lucro}")

    return render_template(
        'controle.html',
        nome=session.get('nome'),  # Inclui o nome do usuário na renderização
        total_receita=total_receita,
        total_despesa=total_despesa,
        total_perda_lucro=total_perda_lucro
    )


#Renderizar (carregar) a página
@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/entrar', methods=['POST'])
def entrar():

    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        cursor = con.cursor()
        try:
            cursor.execute("SELECT u.id_usuario, u.NOME, u.EMAIL, u.SENHA from usuario u WHERE u.EMAIL = ? AND u.SENHA = ?", (email, senha))
            usuario = cursor.fetchone()
        except Exception as e:
            flash('Erro gravissimo')
            return redirect(url_for('login'))
        finally:
            cursor.close()

        if usuario:
            session['id_usuario'] = usuario[0]
            session['nome'] = usuario[1]
            session['email'] = usuario[2]
            return redirect(url_for('controle', usuario=usuario))
        else:
            flash('Email ou senha incorretos')
    return render_template('login.html')


@app.route('/excluir_receita/<int:id>', methods=['GET'])
def excluir_receita(id):
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    cursor = con.cursor()  #Abre o cursor

    # Buscar o  específico para edição
    cursor.execute("SELECT ID_RECEITA, VALOR, DATADIA, FONTE FROM receitas WHERE ID_RECEITA = ?", (id,))
    receita = cursor.fetchone()

    if not receita:
        cursor.close()  # Fecha o cursor se o  não for encontrado
        flash("Receita não encontrada!", "error")
        return redirect(url_for('tabela_receitas'))  # Redireciona para a página principal se o  não for encontrado

    cursor.close()  # Fecha o cursor ao final da função, se não for uma requisição POST
    return render_template('excluir_receita.html', receita=receita, titulo='Excluir Receita')


@app.route('/excluir_despesa/<int:id>', methods=['GET'])
def excluir_despesa(id):
    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    cursor = con.cursor()  # Abre o cursor

    # Buscar o  específico para edição
    cursor.execute("SELECT ID_DESPESAS, VALOR, DATADIA, FONTE FROM despesas WHERE ID_DESPESAS = ?", (id,))
    despesa = cursor.fetchone()

    if not despesa:
        cursor.close()  # Fecha o cursor se o  não for encontrado
        flash("Despesa não encontrada!", "error")
        return redirect(url_for('tabela_despesa'))  # Redireciona para a página principal se o  não for encontrado

    cursor.close()  # Fecha o cursor ao final da função, se não for uma requisição POST
    return render_template('excluir_despesa.html', despesa=despesa, titulo='Excluir Despesa')


@app.route('/sair_conta', methods=['GET'])
def sair_conta():

    id_usuario = session['id_usuario']

    if 'id_usuario' not in session:
        flash('Você precisa estar logado no sistema')
        return redirect(url_for('login'))
    cursor = con.cursor()  # Abre o cursor

    cursor.execute("SELECT ID_USUARIO, NOME, EMAIL, SENHA FROM USUARIO WHERE ID_USUARIO = ?", (id_usuario,))
    usuario = cursor.fetchone()

    if not usuario:
        cursor.close()  # Fecha o cursor se não for encontrado
        flash("Usuário não encontrada!", "error")
        return redirect(url_for('controle'))  # Redireciona para a página principal se o  não for encontrado

    cursor.close()  # Fecha o cursor ao final da função, se não for uma requisição POST
    return render_template('sair_conta.html', usuario=usuario, titulo='Fazer Logout')


# Sair da conta
@app.route('/logout') 
def logout():
    session.pop('id_usuario', None)
    return redirect(url_for('login'))         


if __name__ == '__main__':
    app.run(debug=True)
