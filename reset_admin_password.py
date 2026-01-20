# reset_admin_password.py

import database as db
import auth

# --- Configurações ---
# ALTERE AQUI: O nome do usuário agora é 'coordenador.geral'
ADMIN_USERNAME = 'coordenador.geral'
NEW_PASSWORD = 'admin123'
# ---------------------

print(f"Iniciando o script para redefinir a senha do usuário '{ADMIN_USERNAME}'...")

# 1. Gerar o hash da nova senha usando a mesma função da aplicação
new_hash = auth.hash_password(NEW_PASSWORD)
print(f"Nova senha: '{NEW_PASSWORD}'")
print(f"Hash gerado: {new_hash}")

# 2. Chamar a função do banco de dados para atualizar a senha
print("Conectando ao banco de dados para atualizar a senha...")
success = db.update_user_password(ADMIN_USERNAME, new_hash)

if success:
    print("\nSUCESSO! A senha do administrador foi redefinida.")
    print("Agora você pode fazer login com:")
    print(f"  Usuário: {ADMIN_USERNAME}")
    print(f"  Senha: {NEW_PASSWORD}")
else:
    print("\nFALHA! A senha não foi redefinida. Verifique se o nome de usuário está correto e se o usuário existe no banco.")

