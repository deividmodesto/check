# limpar_banco.py
import database as db

def limpar_submissoes_vazias():
    print("--- Iniciando Limpeza de Submissões Vazias ---")
    
    conn = db.get_connection()
    if not conn:
        print("Erro: Não foi possível conectar ao banco de dados.")
        return

    cursor = conn.cursor()
    
    try:
        # 1. Verifica quantas submissões estão "órfãs" (sem respostas na tabela Respostas)
        query_count = """
            SELECT COUNT(ID) 
            FROM Submissoes 
            WHERE ID NOT IN (SELECT DISTINCT SubmissaoID FROM Respostas)
        """
        cursor.execute(query_count)
        count = cursor.fetchone()[0]

        if count == 0:
            print("O banco de dados está limpo! Nenhuma submissão vazia foi encontrada.")
        else:
            print(f"ATENÇÃO: Foram encontradas {count} submissões (checklists) totalmente vazias.")
            print("Isso geralmente acontece quando as respostas foram apagadas, mas o registro do envio permaneceu.")
            
            confirmacao = input(f"Deseja EXCLUIR permanentemente esses {count} registros? (Digite 'SIM' para confirmar): ")
            
            if confirmacao.upper() == 'SIM':
                # 2. Executa a exclusão
                query_delete = """
                    DELETE FROM Submissoes 
                    WHERE ID NOT IN (SELECT DISTINCT SubmissaoID FROM Respostas)
                """
                cursor.execute(query_delete)
                conn.commit()
                print(f"Sucesso! {count} registros vazios foram removidos.")
            else:
                print("Operação cancelada. Nenhum dado foi apagado.")

    except Exception as e:
        print(f"Erro durante a execução: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    limpar_submissoes_vazias()