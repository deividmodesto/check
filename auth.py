# auth.py
import hashlib

def hash_password(password):
    """Cria um hash SHA-256 para a senha fornecida."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_hash, provided_password):
    """Verifica se a senha fornecida corresponde ao hash armazenado."""
    return stored_hash == hash_password(provided_password)