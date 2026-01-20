# main.py
import getpass
import database as db
import auth

# Variável global para armazenar os dados do usuário logado
current_user = None

def login():
    """Função de login."""
    global current_user
    print("--- Login no Sistema de Checklist ---")
    username = input("Usuário: ")
    password = getpass.getpass("Senha: ") # getpass esconde a senha ao digitar

    user_data = db.get_user_by_username(username)

    if user_data and auth.verify_password(user_data.SenhaHash, password):
        current_user = user_data
        print(f"\nBem-vindo(a), {current_user.NomeUsuario}!")
        return True
    else:
        print("\nUsuário ou senha inválidos.")
        return False

def show_gestor_menu():
    """Menu para usuários GESTOR."""
    while True:
        print("\n--- Menu do Gestor ---")
        print(f"Departamento: {current_user.DepartamentoNome}")
        print("1. Criar novo Checklist")
        print("2. Ver respostas dos Checklists")
        print("3. Criar novo Usuário")
        print("4. Sair (Logout)")
        choice = input("Escolha uma opção: ")

        if choice == '1':
            create_checklist_flow()
        elif choice == '2':
            view_responses_flow()
        elif choice == '3':
            create_user_flow()
        elif choice == '4':
            break
        else:
            print("Opção inválida.")

def show_colaborador_menu():
    """Menu para usuários COLABORADOR."""
    while True:
        print("\n--- Menu do Colaborador ---")
        print(f"Departamento: {current_user.DepartamentoNome}")
        print("1. Preencher um Checklist")
        print("2. Sair (Logout)")
        choice = input("Escolha uma opção: ")

        if choice == '1':
            fill_checklist_flow()
        elif choice == '2':
            break
        else:
            print("Opção inválida.")

# --- Fluxos do Gestor ---

def create_user_flow():
    print("\n--- Criação de Novo Usuário ---")
    username = input("Nome do novo usuário: ")
    password = getpass.getpass("Senha para o novo usuário: ")
    password_hash = auth.hash_password(password)

    print("Papéis disponíveis: GESTOR, COLABORADOR")
    role = input("Papel do usuário: ").upper()
    if role not in ['GESTOR', 'COLABORADOR']:
        print("Papel inválido.")
        return

    # No nosso sistema simples, um gestor só cria usuários para o seu próprio departamento.
    if db.create_user(username, password_hash, role, current_user.DepartamentoID):
        print("Usuário criado com sucesso!")
    else:
        print("Erro ao criar usuário (talvez o nome de usuário já exista).")

def create_checklist_flow():
    print("\n--- Criação de Novo Checklist ---")
    title = input("Título do checklist: ")
    questions = []
    print("Digite as perguntas. Deixe em branco e pressione Enter para finalizar.")
    while True:
        q = input(f"Pergunta {len(questions) + 1}: ")
        if not q:
            break
        questions.append(q)

    if db.create_checklist(title, current_user.DepartamentoID, questions):
        print("Checklist criado com sucesso!")
    else:
        print("Falha ao criar o checklist.")

def view_responses_flow():
    print("\n--- Respostas dos Checklists ---")
    submissions = db.get_checklist_submissions(current_user.DepartamentoID)
    if not submissions:
        print("Nenhuma resposta encontrada para este departamento.")
        return

    for i, sub in enumerate(submissions):
        print(f"{i+1}. Checklist: '{sub.Titulo}' | Respondido por: {sub.NomeUsuario} em {sub.DataSubmissao.strftime('%d/%m/%Y %H:%M')}")

    try:
        choice = int(input("\nDigite o número da resposta para ver os detalhes (ou 0 para voltar): "))
        if 0 < choice <= len(submissions):
            selected_submission_id = submissions[choice-1].ID
            details = db.get_submission_details(selected_submission_id)
            print("\n--- Detalhes da Resposta ---")
            for detail in details:
                print(f"Pergunta: {detail.TextoPergunta}")
                print(f"Resposta: {detail.Resposta}\n")
    except (ValueError, IndexError):
        print("Seleção inválida.")


# --- Fluxos do Colaborador ---

def fill_checklist_flow():
    print("\n--- Preencher Checklist ---")
    checklists = db.get_checklists_by_department(current_user.DepartamentoID)
    if not checklists:
        print("Nenhum checklist disponível para o seu departamento.")
        return

    for i, chk in enumerate(checklists):
        print(f"{i+1}. {chk.Titulo}")

    try:
        choice = int(input("\nEscolha o checklist para preencher: "))
        if 0 < choice <= len(checklists):
            selected_checklist_id = checklists[choice-1].ID
            questions = db.get_questions_for_checklist(selected_checklist_id)
            answers = {}
            print("\n--- Responda as perguntas (Sim/Não) ---")
            for q in questions:
                answer = input(f"{q.TextoPergunta}: ")
                answers[q.ID] = answer # Armazena o ID da pergunta e a resposta

            if db.save_checklist_response(selected_checklist_id, current_user.ID, answers):
                print("\nChecklist respondido e salvo com sucesso!")
            else:
                print("\nErro ao salvar as respostas.")

    except (ValueError, IndexError):
        print("Seleção inválida.")


# --- Execução Principal ---
if __name__ == "__main__":
    while True:
        if current_user:
            # Redireciona para o menu correto baseado no papel do usuário
            if current_user.Papel == 'GESTOR':
                show_gestor_menu()
            elif current_user.Papel == 'COLABORADOR':
                show_colaborador_menu()

            # Após sair do menu (logout)
            current_user = None
            print("Logout realizado com sucesso.\n")
        else:
            if not login():
                # Permite tentar o login novamente ou sair
                retry = input("Tentar novamente? (s/n): ").lower()
                if retry != 's':
                    break
            print("-" * 20)