# app_gui.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QDialog, QComboBox, QMessageBox,
    QListWidget, QListWidgetItem, QFormLayout, QTextEdit
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

# Importamos nossas funções de back-end
import database as db
import auth

# --- Janela de Login ---
class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistema de Checklist - Login")
        self.setGeometry(100, 100, 400, 200)

        # Widget central para organizar o layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Campos de usuário e senha
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nome de usuário")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password) # Esconde a senha

        # Botão de login
        login_button = QPushButton("Entrar")
        login_button.clicked.connect(self.handle_login)

        # Mensagem de erro (inicialmente vazia)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")

        # Adicionando widgets ao layout
        layout.addWidget(QLabel("Usuário:"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Senha:"))
        layout.addWidget(self.password_input)
        layout.addWidget(login_button)
        layout.addWidget(self.error_label)
        
        self.main_window = None # Para guardar a referência da próxima janela

    def handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        user_data = db.get_user_by_username(username)

        if user_data and auth.verify_password(user_data.SenhaHash, password):
            # Se o login for bem-sucedido, feche a janela de login
            # e abra a janela principal correspondente
            self.error_label.setText("")
            
            if user_data.Papel == 'GESTOR':
                self.main_window = GestorWindow(user_data)
            else:
                self.main_window = ColaboradorWindow(user_data)
            
            self.main_window.show()
            self.close()
        else:
            self.error_label.setText("Usuário ou senha inválidos.")

# --- Janela Principal do Gestor ---
class GestorWindow(QMainWindow):
    def __init__(self, user_data):
        super().__init__()
        self.user_data = user_data
        self.setWindowTitle(f"Menu do Gestor - {self.user_data.NomeUsuario}")
        self.setGeometry(100, 100, 500, 300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Título da janela
        title_label = QLabel(f"Bem-vindo, Gestor do Depto. {self.user_data.DepartamentoNome}!")
        title_label.setFont(QFont("Arial", 16))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Botões de ação
        btn_create_checklist = QPushButton("Criar Novo Checklist")
        btn_view_responses = QPushButton("Ver Respostas de Checklists")
        btn_create_user = QPushButton("Criar Novo Usuário")
        
        # Conectando os botões às suas funções (que abrirão novas janelas/diálogos)
        btn_create_user.clicked.connect(self.open_create_user_dialog)
        # (As outras conexões seguiriam o mesmo padrão)
        # btn_create_checklist.clicked.connect(self.open_create_checklist_dialog)
        # btn_view_responses.clicked.connect(self.open_view_responses_window)


        layout.addWidget(title_label)
        layout.addWidget(btn_create_checklist)
        layout.addWidget(btn_view_responses)
        layout.addWidget(btn_create_user)
    
    def open_create_user_dialog(self):
        # Abre a janela de diálogo para criar um usuário
        # Passamos o ID do departamento do gestor para o diálogo
        dialog = CreateUserDialog(self.user_data.DepartamentoID)
        # O método exec() torna o diálogo modal (bloqueia a janela principal)
        dialog.exec()

# --- Janela Principal do Colaborador (Exemplo de estrutura) ---
class ColaboradorWindow(QMainWindow):
    def __init__(self, user_data):
        super().__init__()
        self.user_data = user_data
        self.setWindowTitle(f"Menu do Colaborador - {self.user_data.NomeUsuario}")
        self.setGeometry(100, 100, 500, 200)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        title_label = QLabel(f"Bem-vindo, {self.user_data.NomeUsuario}!")
        title_label.setFont(QFont("Arial", 16))
        
        btn_fill_checklist = QPushButton("Preencher um Checklist")
        # btn_fill_checklist.clicked.connect(self.open_fill_checklist_window)
        
        layout.addWidget(title_label)
        layout.addWidget(btn_fill_checklist)

# --- Diálogo para Criar um Novo Usuário ---
class CreateUserDialog(QDialog):
    def __init__(self, department_id):
        super().__init__()
        self.department_id = department_id
        self.setWindowTitle("Criar Novo Usuário")
        self.layout = QFormLayout(self) # Layout de formulário (label: input)

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.role_combo = QComboBox()
        self.role_combo.addItems(['COLABORADOR', 'GESTOR'])

        self.layout.addRow("Nome de Usuário:", self.username_input)
        self.layout.addRow("Senha:", self.password_input)
        self.layout.addRow("Papel:", self.role_combo)

        # Botões de Salvar e Cancelar
        button_box = QHBoxLayout()
        btn_save = QPushButton("Salvar")
        btn_cancel = QPushButton("Cancelar")
        
        btn_save.clicked.connect(self.save_user)
        btn_cancel.clicked.connect(self.reject) # self.reject fecha o diálogo

        button_box.addWidget(btn_save)
        button_box.addWidget(btn_cancel)
        self.layout.addRow(button_box)

    def save_user(self):
        username = self.username_input.text()
        password = self.password_input.text()
        role = self.role_combo.currentText()

        if not username or not password:
            QMessageBox.warning(self, "Erro", "Nome de usuário e senha não podem estar vazios.")
            return

        password_hash = auth.hash_password(password)
        
        # Usa a função do banco de dados para criar o usuário
        if db.create_user(username, password_hash, role, self.department_id):
            QMessageBox.information(self, "Sucesso", "Usuário criado com sucesso!")
            self.accept() # self.accept também fecha o diálogo
        else:
            QMessageBox.critical(self, "Erro", "Falha ao criar usuário. O nome de usuário pode já existir.")


# --- Ponto de Entrada da Aplicação ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    login_win = LoginWindow()
    login_win.show()
    sys.exit(app.exec())