# database.py
import pyodbc
from config import DB_CONFIG

# --- Funções de Conexão e de Usuário/Setor ---
def get_connection():
    try:
        conn_str = ';'.join([f'{k}={v}' for k, v in DB_CONFIG.items()])
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        print(f"Erro de Conexão com o Banco de Dados: {sqlstate}")
        return None

def get_user_by_username(username):
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor()
    query = "SELECT ID, NomeUsuario, SenhaHash, Papel, CoordenadorID FROM Usuarios WHERE NomeUsuario = ?"
    cursor.execute(query, username)
    row = cursor.fetchone()
    conn.close()
    return row

def create_user(username, password_hash, role, coordinator_id=None):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        query = "INSERT INTO Usuarios (NomeUsuario, SenhaHash, Papel, CoordenadorID) VALUES (?, ?, ?, ?)"
        cursor.execute(query, username, password_hash, role, coordinator_id)
        conn.commit()
        return True
    except pyodbc.IntegrityError: return False
    finally: conn.close()
    
def get_user_by_id(user_id):
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor()
    query = "SELECT ID, NomeUsuario, Papel, CoordenadorID FROM Usuarios WHERE ID = ?"
    cursor.execute(query, user_id)
    row = cursor.fetchone()
    conn.close()
    return row

def update_user_info(user_id, username, role, coordinator_id):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        query = "UPDATE Usuarios SET NomeUsuario = ?, Papel = ?, CoordenadorID = ? WHERE ID = ?"
        cursor.execute(query, username, role, coordinator_id, user_id)
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar usuário: {e}")
        conn.rollback()
        return False
    finally: conn.close()

def update_user_password(user_id, new_password_hash):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Usuarios SET SenhaHash = ? WHERE ID = ?", new_password_hash, user_id)
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao resetar a senha: {e}")
        conn.rollback()
        return False
    finally: conn.close()

def get_manageable_users(coordinator_id):
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = "SELECT ID, NomeUsuario, Papel FROM Usuarios WHERE CoordenadorID = ?"
    cursor.execute(query, coordinator_id)
    rows = cursor.fetchall()
    conn.close()
    return rows
    
def get_all_coordinators():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = "SELECT ID, NomeUsuario FROM Usuarios WHERE Papel IN ('COORDENADOR', 'GESTOR')"
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_collaborators_for_coordinator(coordinator_id):
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("SELECT ID, NomeUsuario FROM Usuarios WHERE CoordenadorID = ?", coordinator_id)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_sectors():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("SELECT ID, Nome FROM Setores")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_sectors_for_coordinator(coordinator_id):
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = "SELECT S.ID, S.Nome FROM Setores S JOIN Coordenadores_Setores CS ON S.ID = CS.SetorID WHERE CS.UsuarioID = ?"
    cursor.execute(query, coordinator_id)
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_coordinator_sectors(coordinator_id, sector_ids):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Coordenadores_Setores WHERE UsuarioID = ?", coordinator_id)
        if sector_ids:
            for sector_id in sector_ids:
                cursor.execute("INSERT INTO Coordenadores_Setores (UsuarioID, SetorID) VALUES (?, ?)", coordinator_id, sector_id)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally: conn.close()

def create_sector(sector_name):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        query = "INSERT INTO Setores (Nome) VALUES (?)"
        cursor.execute(query, sector_name)
        conn.commit()
        return True
    except pyodbc.IntegrityError: return False
    finally: conn.close()


# --- Funções de Gerenciamento de Tipos de Resposta ---
def create_response_type(name, options):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute("SET NOCOUNT ON; INSERT INTO TiposResposta (Nome, TipoInput) VALUES (?, 'radio'); SELECT SCOPE_IDENTITY();", name)
        response_type_id = cursor.fetchone()[0]
        for option in options:
            if option:
                cursor.execute("INSERT INTO OpcoesResposta (TipoRespostaID, TextoOpcao) VALUES (?, ?)", response_type_id, option)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally: conn.close()

def get_all_response_types():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("SELECT ID, Nome, TipoInput FROM TiposResposta ORDER BY Nome")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_response_type(response_type_id):
    """
    Apaga um tipo de resposta e todas as suas dependências (opções, associações
    e principalmente as respostas já enviadas que o utilizam) de forma transacional.
    """
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        # Inicia uma transação para garantir que todas as operações sejam executadas
        # em conjunto. Se uma falhar, todas são desfeitas.
        conn.autocommit = False

        # Passo 1: Apagar as respostas JÁ ENVIADAS que usam este TipoRespostaID.
        # Esta é a dependência que estava causando o erro persistente.
        cursor.execute("DELETE FROM Respostas WHERE TipoRespostaID = ?", response_type_id)

        # Passo 2: Apagar as associações na tabela 'Componente_TiposResposta'.
        # Isso desconecta o tipo de resposta dos modelos de checklist.
        cursor.execute("DELETE FROM Componente_TiposResposta WHERE TipoRespostaID = ?", response_type_id)

        # Passo 3: Apagar as opções de resposta (ex: "Sim", "Não") associadas.
        # A tabela OpcoesResposta também depende do TipoResposta.
        cursor.execute("DELETE FROM OpcoesResposta WHERE TipoRespostaID = ?", response_type_id)

        # Passo 4: Finalmente, apagar o tipo de resposta principal.
        # Agora que não há mais dependências, esta operação funcionará.
        cursor.execute("DELETE FROM TiposResposta WHERE ID = ?", response_type_id)

        # Se todos os comandos foram bem-sucedidos, salva as alterações no banco.
        conn.commit()
        return True
    except Exception as e:
        # Se ocorrer qualquer erro, desfaz todas as alterações.
        print(f"Erro ao deletar o tipo de resposta: {e}")
        conn.rollback()
        return False
    finally:
        # Garante que o modo autocommit seja restaurado e a conexão fechada.
        conn.autocommit = True
        conn.close()


# --- NOVAS FUNÇÕES DE CHECKLIST (SUPORTE A MÚLTIPLAS RESPOSTAS) ---
def create_flexible_checklist(title, sector_id, components_data):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        sql_checklist = "SET NOCOUNT ON; INSERT INTO Checklists (Titulo, SetorID) VALUES (?, ?); SELECT SCOPE_IDENTITY();"
        cursor.execute(sql_checklist, title, sector_id)
        checklist_id = cursor.fetchone()[0]
        for order, comp in enumerate(components_data):
            sql_component = "SET NOCOUNT ON; INSERT INTO ComponentesChecklist (ChecklistID, ParentID, TextoComponente, TipoComponente, Instrucao, Ordem) VALUES (?, NULL, ?, ?, ?, ?); SELECT SCOPE_IDENTITY();"
            cursor.execute(sql_component, checklist_id, comp['text'], comp['type'], comp.get('instruction'), order)
            parent_id = cursor.fetchone()[0]
            if 'response_type_ids' in comp:
                for rt_id in comp['response_type_ids']:
                    cursor.execute("INSERT INTO Componente_TiposResposta (ComponenteID, TipoRespostaID) VALUES (?, ?)", parent_id, rt_id)
            if comp['type'] == 'CATEGORIA' and 'sub_items' in comp:
                for sub_order, sub_item in enumerate(comp['sub_items']):
                    sql_sub_item = "SET NOCOUNT ON; INSERT INTO ComponentesChecklist (ChecklistID, ParentID, TextoComponente, TipoComponente, Instrucao, Ordem) VALUES (?, ?, ?, 'ITEM_VERIFICACAO', ?, ?); SELECT SCOPE_IDENTITY();"
                    cursor.execute(sql_sub_item, checklist_id, parent_id, sub_item['text'], sub_item.get('instruction'), sub_order)
                    sub_item_id = cursor.fetchone()[0]
                    if 'response_type_ids' in sub_item:
                        for rt_id in sub_item['response_type_ids']:
                            cursor.execute("INSERT INTO Componente_TiposResposta (ComponenteID, TipoRespostaID) VALUES (?, ?)", sub_item_id, rt_id)
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao criar checklist flexível: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_flexible_checklist(checklist_id, title, sector_id, components_data):
    """
    Atualiza um checklist. AGORA PROTEGIDO: Impede alteração estrutural se houver respostas.
    """
    conn = get_connection()
    if not conn: return False, "Erro de conexão com o banco."
    cursor = conn.cursor()
    try:
        # 1. VERIFICAÇÃO DE SEGURANÇA (NOVO)
        # Verifica se já existem submissões para este checklist
        cursor.execute("SELECT COUNT(ID) FROM Submissoes WHERE ChecklistID = ?", checklist_id)
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Se já tem respostas, NÃO permite mexer nas perguntas, pois isso apagaria o histórico.
            # Permite apenas atualizar Título e Setor, se necessário, mas bloqueia a recriação dos componentes.
            # Para simplificar e garantir segurança total, bloqueamos a edição completa e avisamos o usuário.
            return False, f"PROTEÇÃO DE DADOS: Este checklist já foi respondido {count} vezes. Alterar as perguntas agora apagaria as respostas antigas. Por favor, crie um NOVO checklist."

        # Se não tem respostas, prossegue com a lógica original (apagando e recriando)
        conn.autocommit = False

        # Atualiza o título e setor
        cursor.execute("UPDATE Checklists SET Titulo = ?, SetorID = ? WHERE ID = ?", title, sector_id, checklist_id)
        
        # Limpa componentes antigos (seguro pois não há respostas vinculadas)
        cursor.execute("DELETE FROM ComponentesChecklist WHERE ChecklistID = ?", checklist_id)

        # Reinsere os componentes
        for order, comp in enumerate(components_data):
            sql_component = """
            SET NOCOUNT ON;
            INSERT INTO ComponentesChecklist (ChecklistID, ParentID, TextoComponente, TipoComponente, Instrucao, Ordem) 
            VALUES (?, NULL, ?, ?, ?, ?);
            SELECT SCOPE_IDENTITY();
            """
            cursor.execute(sql_component, checklist_id, comp['text'], comp['type'], comp.get('instruction'), order)
            parent_id = cursor.fetchone()[0]

            if 'response_type_ids' in comp:
                for rt_id in comp['response_type_ids']:
                    cursor.execute("INSERT INTO Componente_TiposResposta (ComponenteID, TipoRespostaID) VALUES (?, ?)", parent_id, rt_id)

            if comp['type'] == 'CATEGORIA' and 'sub_items' in comp:
                for sub_order, sub_item in enumerate(comp['sub_items']):
                    sql_sub_item = "SET NOCOUNT ON; INSERT INTO ComponentesChecklist (ChecklistID, ParentID, TextoComponente, TipoComponente, Instrucao, Ordem) VALUES (?, ?, ?, 'ITEM_VERIFICACAO', ?, ?); SELECT SCOPE_IDENTITY();"
                    cursor.execute(sql_sub_item, checklist_id, parent_id, sub_item['text'], sub_item.get('instruction'), sub_order)
                    sub_item_id = cursor.fetchone()[0]
                    
                    if 'response_type_ids' in sub_item:
                        for rt_id in sub_item['response_type_ids']:
                            cursor.execute("INSERT INTO Componente_TiposResposta (ComponenteID, TipoRespostaID) VALUES (?, ?)", sub_item_id, rt_id)
        
        conn.commit()
        return True, "Checklist atualizado com sucesso!"
    except Exception as e:
        print(f"Erro ao atualizar checklist: {e}")
        conn.rollback()
        return False, f"Erro interno ao atualizar: {str(e)}"
    finally:
        conn.autocommit = True
        conn.close()

def get_response_type_by_id(type_id):
    """Busca um único tipo de resposta e suas opções associadas."""
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor()
    
    # Busca o nome do tipo de resposta
    cursor.execute("SELECT ID, Nome FROM TiposResposta WHERE ID = ?", type_id)
    response_type = cursor.fetchone()
    if not response_type:
        conn.close()
        return None
        
    # Busca as opções associadas
    cursor.execute("SELECT ID, TextoOpcao, IsConforme FROM OpcoesResposta WHERE TipoRespostaID = ?", type_id)
    options = cursor.fetchall()
    
    conn.close()
    return {'details': response_type, 'options': options}

def update_response_type(type_id, name, options):
    """Atualiza um tipo de resposta (nome e opções)."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        # 1. Atualiza o nome
        cursor.execute("UPDATE TiposResposta SET Nome = ? WHERE ID = ?", name, type_id)
        
        # 2. Apaga as opções antigas (estratégia "apagar e recriar")
        cursor.execute("DELETE FROM OpcoesResposta WHERE TipoRespostaID = ?", type_id)
        
        # 3. Insere as novas opções
        for option in options:
            cursor.execute(
                "INSERT INTO OpcoesResposta (TipoRespostaID, TextoOpcao, IsConforme) VALUES (?, ?, ?)",
                type_id,
                option['text'],
                option['is_conforme']
            )
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar tipo de resposta: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_flexible_checklist_for_filling(checklist_id):
    conn = get_connection()
    if not conn: return None
    cursor_title = conn.cursor()
    cursor_title.execute("SELECT Titulo, SetorID FROM Checklists WHERE ID = ?", checklist_id)
    checklist_row = cursor_title.fetchone()
    if not checklist_row: return None
    checklist_data = {'ID': checklist_id, 'Titulo': checklist_row.Titulo, 'Componentes': []}
    cursor_comps = conn.cursor()
    query_components = "SELECT ID, ParentID, TextoComponente, TipoComponente, Instrucao FROM ComponentesChecklist WHERE ChecklistID = ? ORDER BY Ordem, ParentID, ID"
    cursor_comps.execute(query_components, checklist_id)
    all_components = cursor_comps.fetchall()
    component_map = {}
    for comp in all_components:
        cursor_rt = conn.cursor()
        query_rt = "SELECT tr.ID, tr.Nome, tr.TipoInput FROM TiposResposta tr JOIN Componente_TiposResposta ctr ON tr.ID = ctr.TipoRespostaID WHERE ctr.ComponenteID = ? ORDER BY tr.ID"
        cursor_rt.execute(query_rt, comp.ID)
        response_types = cursor_rt.fetchall()
        response_types_with_options = []
        for rt in response_types:
            options = []
            if rt.TipoInput == 'radio':
                cursor_options = conn.cursor()
                cursor_options.execute("SELECT TextoOpcao FROM OpcoesResposta WHERE TipoRespostaID = ?", rt.ID)
                options = [row.TextoOpcao for row in cursor_options.fetchall()]
            response_types_with_options.append({'details': rt, 'options': options})
        component_map[comp.ID] = {'data': comp, 'children': [], 'response_types': response_types_with_options}
    structured_list = []
    for comp_data in list(component_map.values()):
        parent_id = comp_data['data'].ParentID
        if parent_id and parent_id in component_map:
            component_map[parent_id]['children'].append(comp_data)
        else:
            structured_list.append(comp_data)
    checklist_data['Componentes'] = structured_list
    conn.close()
    return checklist_data

def save_flexible_checklist_response(checklist_id, user_id, answers, participants):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        sql_batch = "SET NOCOUNT ON; INSERT INTO Submissoes (ChecklistID, UsuarioID, NomeTrabalhadorAuditado, NomeResponsavelArea) VALUES (?, ?, ?, ?); SELECT SCOPE_IDENTITY();"
        cursor.execute(sql_batch, checklist_id, user_id, participants['worker_name'], participants['area_manager_name'])
        submission_id = cursor.fetchone()[0]
        for component_id, data in answers.items():
            responses = data.get('responses', {})
            observation = data.get('observation')
            is_first_response = True
            for rt_id, answer_value in responses.items():
                obs_to_save = observation if is_first_response else None
                sql_get_id = "SET NOCOUNT ON; INSERT INTO Respostas (SubmissaoID, ComponenteID, TipoRespostaID, Resposta, Observacao) VALUES (?, ?, ?, ?, ?); SELECT SCOPE_IDENTITY();"
                if isinstance(answer_value, list):
                    placeholder_text = f"{len(answer_value)} foto(s) anexada(s)"
                    cursor.execute(sql_get_id, submission_id, component_id, rt_id, placeholder_text, obs_to_save)
                    resposta_id = cursor.fetchone()[0]
                    for photo_path in answer_value:
                        cursor.execute("INSERT INTO FotosResposta (RespostaID, CaminhoFoto) VALUES (?, ?)", resposta_id, photo_path)
                else:
                    cursor.execute(sql_get_id, submission_id, component_id, rt_id, answer_value, obs_to_save)
                is_first_response = False
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao salvar respostas do checklist flexível: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_checklists_for_collaborator(collaborator_id):
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = "SELECT C.ID, C.Titulo FROM Checklists C WHERE C.SetorID IN (SELECT CS.SetorID FROM Coordenadores_Setores CS WHERE CS.UsuarioID = (SELECT U.CoordenadorID FROM Usuarios U WHERE U.ID = ?))"
    cursor.execute(query, collaborator_id)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_checklists_for_coordinator(coordinator_id):
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = "SELECT c.ID, c.Titulo, s.Nome as NomeSetor FROM Checklists c JOIN Setores s ON c.SetorID = s.ID WHERE c.SetorID IN (SELECT cs.SetorID FROM Coordenadores_Setores cs WHERE cs.UsuarioID = ?) ORDER BY s.Nome, c.Titulo"
    cursor.execute(query, coordinator_id)
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_checklist(checklist_id):
    conn = get_connection()
    if not conn: return (False, "Falha na conexão com o banco de dados.")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(ID) FROM Submissoes WHERE ChecklistID = ?", checklist_id)
        submission_count = cursor.fetchone()[0]
        if submission_count > 0:
            return (False, "Este checklist não pode ser apagado pois já possui respostas enviadas.")
        cursor.execute("DELETE FROM Checklists WHERE ID = ?", checklist_id)
        conn.commit()
        return (True, "Checklist apagado com sucesso.")
    except Exception as e:
        conn.rollback()
        return (False, "Ocorreu um erro ao tentar apagar o checklist.")
    finally: conn.close()

def get_submissions_for_collaborator(collaborator_id):
    """Busca o histórico de submissões ATIVAS para um colaborador específico."""
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = """
        SELECT sub.ID, chk.Titulo, sub.DataSubmissao
        FROM Submissoes sub
        JOIN Checklists chk ON sub.ChecklistID = chk.ID
        WHERE sub.UsuarioID = ?
        AND sub.Status = 'Ativa' -- CORREÇÃO AQUI: Filtra apenas as versões ativas
        ORDER BY sub.DataSubmissao DESC
    """
    cursor.execute(query, collaborator_id)
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_submission(submission_id):
    """Apaga uma submissão e suas respostas, cuidando do histórico de versionamento."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        # Inicia a transação para garantir que ambas as operações funcionem
        conn.autocommit = False

        # 1. "Desarquiva" a versão anterior, se houver.
        #    Procura por uma submissão que foi substituída por esta que estamos apagando.
        cursor.execute("""
            UPDATE Submissoes 
            SET Status = 'Ativa', SubstituidaPorID = NULL 
            WHERE SubstituidaPorID = ?
        """, submission_id)

        # 2. Agora, apaga a submissão desejada.
        #    A exclusão em cascata cuidará das respostas e fotos.
        cursor.execute("DELETE FROM Submissoes WHERE ID = ?", submission_id)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao apagar submissão: {e}")
        conn.rollback()
        return False
    finally:
        conn.autocommit = True
        conn.close()

def get_submissions_for_coordinator(coordinator_id):
    """Busca todas as submissões ATIVAS para os setores de um coordenador."""
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = """
        SELECT sub.ID, chk.Titulo, usr.NomeUsuario, sub.DataSubmissao
        FROM Submissoes sub
        JOIN Usuarios usr ON sub.UsuarioID = usr.ID
        JOIN Checklists chk ON sub.ChecklistID = chk.ID
        WHERE chk.SetorID IN (SELECT cs.SetorID FROM Coordenadores_Setores cs WHERE cs.UsuarioID = ?)
        AND sub.Status = 'Ativa' -- Garante que apenas as versões ativas sejam mostradas
        ORDER BY sub.DataSubmissao DESC
    """
    cursor.execute(query, coordinator_id)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_submission_details(submission_id):
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor()
    query_header = "SELECT s.ID, chk.ID as ChecklistID, chk.Titulo, u.NomeUsuario, u.ID as UsuarioID, s.DataSubmissao, s.NomeTrabalhadorAuditado, s.NomeResponsavelArea FROM Submissoes s JOIN Checklists chk ON s.ChecklistID = chk.ID JOIN Usuarios u ON s.UsuarioID = u.ID WHERE s.ID = ?"
    cursor.execute(query_header, submission_id)
    header = cursor.fetchone()
    if not header:
        conn.close()
        return None
    cursor.execute("SELECT ID, ParentID, TextoComponente, Instrucao, TipoComponente, Ordem FROM ComponentesChecklist WHERE ChecklistID = ? ORDER BY Ordem", header.ChecklistID)
    all_components_structure = cursor.fetchall()
    components = {comp.ID: {'data': comp, 'answers': [], 'children': []} for comp in all_components_structure}
    query_answers = "SELECT r.ID as RespostaID, r.ComponenteID, r.Resposta, r.Observacao, tr.Nome as TipoRespostaNome, tr.TipoInput, op.IsConforme, fr.CaminhoFoto FROM Respostas r LEFT JOIN TiposResposta tr ON r.TipoRespostaID = tr.ID LEFT JOIN OpcoesResposta op ON tr.ID = op.TipoRespostaID AND r.Resposta = op.TextoOpcao LEFT JOIN FotosResposta fr ON r.ID = fr.RespostaID WHERE r.SubmissaoID = ?"
    cursor.execute(query_answers, submission_id)
    all_answers_flat = cursor.fetchall()
    answers_grouped = {}
    for row in all_answers_flat:
        if row.RespostaID not in answers_grouped:
            answers_grouped[row.RespostaID] = {'component_id': row.ComponenteID, 'tipo_nome': row.TipoRespostaNome, 'tipo_input': row.TipoInput, 'valor': row.Resposta, 'observacao': row.Observacao, 'is_conforme': row.IsConforme, 'fotos': []}
        if row.CaminhoFoto:
            answers_grouped[row.RespostaID]['fotos'].append(row.CaminhoFoto)
    for resp_id, answer_data in answers_grouped.items():
        comp_id = answer_data['component_id']
        if comp_id in components:
            components[comp_id]['answers'].append(answer_data)
    structured_list = []
    for comp_id, comp_data in components.items():
        parent_id = comp_data['data'].ParentID
        if parent_id and parent_id in components:
            components[parent_id]['children'].append(comp_data)
        elif not parent_id:
            structured_list.append(comp_data)
    conn.close()
    return {'header': header, 'details': structured_list}

def get_filtered_submissions(coordinator_id, checklist_id=None, user_id=None, start_date=None, end_date=None, question=None, answer=None):
    """Busca submissões filtradas, retornando uma lista de dicionários."""
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()

    query = """
        SELECT 
            s.ID as SubmissaoID, s.DataSubmissao, c.Titulo as ChecklistTitulo, 
            u.NomeUsuario, comp.TextoComponente, tr.Nome AS TipoRespostaNome, 
            r.Resposta, r.Observacao, op.IsConforme,
            (SELECT STRING_AGG(fr.CaminhoFoto, ',') FROM FotosResposta fr WHERE fr.RespostaID = r.ID) as CaminhosFotos
        FROM Submissoes s
        JOIN Checklists c ON s.ChecklistID = c.ID
        JOIN Usuarios u ON s.UsuarioID = u.ID
        JOIN Respostas r ON r.SubmissaoID = s.ID
        -- CORREÇÃO AQUI: Corrigido o erro de digitação no nome da coluna
        JOIN ComponentesChecklist comp ON r.ComponenteID = comp.ID
        LEFT JOIN TiposResposta tr ON r.TipoRespostaID = tr.ID
        LEFT JOIN OpcoesResposta op ON tr.ID = op.TipoRespostaID AND r.Resposta = op.TextoOpcao
        WHERE u.CoordenadorID = ?
    """
    params = [coordinator_id]

    if checklist_id: query += " AND s.ChecklistID = ?"; params.append(checklist_id)
    if user_id: query += " AND s.UsuarioID = ?"; params.append(user_id)
    if start_date: query += " AND s.DataSubmissao >= ?"; params.append(start_date)
    if end_date: query += " AND s.DataSubmissao < DATEADD(day, 1, ?)"; params.append(end_date)
    if question: query += " AND comp.TextoComponente = ?"; params.append(question)
    if answer: query += " AND r.Resposta LIKE ?"; params.append(f"%{answer}%")
    
    query += " ORDER BY s.DataSubmissao DESC, u.NomeUsuario, comp.Ordem"
    
    cursor.execute(query, params)
    
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    conn.close()
    return results

def get_all_distinct_questions(coordinator_id):
    """Busca todos os textos de perguntas/itens únicos dos checklists de um coordenador."""
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor()
    query = """
        SELECT DISTINCT comp.TextoComponente
        FROM ComponentesChecklist comp
        JOIN Checklists c ON comp.ChecklistID = c.ID
        WHERE comp.TipoComponente IN ('PERGUNTA_SIMPLES', 'ITEM_VERIFICACAO')
        AND c.SetorID IN (SELECT cs.SetorID FROM Coordenadores_Setores cs WHERE cs.UsuarioID = ?)
        ORDER BY comp.TextoComponente
    """
    cursor.execute(query, coordinator_id)
    rows = [row.TextoComponente for row in cursor.fetchall()]
    conn.close()
    return rows

def get_checklist_for_editing(checklist_id):
    """Busca um checklist e seus componentes para o formulário de edição."""
    # Reutiliza a função de preenchimento, pois a estrutura de dados é a mesma.
    return get_flexible_checklist_for_filling(checklist_id)

def replicate_submission_for_editing(old_submission_id, user_id):
    """
    Cria uma cópia exata de uma submissão, arquiva a original e retorna o ID da nova versão.
    """
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor()
    try:
        # Pega os dados da submissão original
        cursor.execute("SELECT ChecklistID, UsuarioID FROM Submissoes WHERE ID = ?", old_submission_id)
        original_sub = cursor.fetchone()
        if not original_sub: return None

        # 1. Cria a nova submissão (a cópia)
        sql_insert_new = "SET NOCOUNT ON; INSERT INTO Submissoes (ChecklistID, UsuarioID, Status) VALUES (?, ?, 'Ativa'); SELECT SCOPE_IDENTITY();"
        cursor.execute(sql_insert_new, original_sub.ChecklistID, user_id) # O autor da nova versão é o usuário logado
        new_submission_id = cursor.fetchone()[0]

        # 2. Arquiva a submissão original, ligando-a à nova
        cursor.execute("UPDATE Submissoes SET Status = 'Arquivada', SubstituidaPorID = ? WHERE ID = ?", new_submission_id, old_submission_id)

        # 3. Copia todas as respostas da submissão antiga para a nova
        cursor.execute("SELECT ComponenteID, TipoRespostaID, Resposta, Observacao FROM Respostas WHERE SubmissaoID = ?", old_submission_id)
        original_answers = cursor.fetchall()
        
        for answer in original_answers:
            sql_copy_answer = "SET NOCOUNT ON; INSERT INTO Respostas (SubmissaoID, ComponenteID, TipoRespostaID, Resposta, Observacao) VALUES (?, ?, ?, ?, ?); SELECT SCOPE_IDENTITY();"
            cursor.execute(sql_copy_answer, new_submission_id, answer.ComponenteID, answer.TipoRespostaID, answer.Resposta, answer.Observacao)
            new_answer_id = cursor.fetchone()[0]

            # 4. Se a resposta original tinha fotos, copia as fotos para a nova resposta
            cursor.execute("SELECT CaminhoFoto FROM FotosResposta WHERE RespostaID = (SELECT ID FROM Respostas WHERE SubmissaoID = ? AND ComponenteID = ? AND TipoRespostaID = ?)", old_submission_id, answer.ComponenteID, answer.TipoRespostaID)
            original_photos = cursor.fetchall()
            for photo in original_photos:
                cursor.execute("INSERT INTO FotosResposta (RespostaID, CaminhoFoto) VALUES (?, ?)", new_answer_id, photo.CaminhoFoto)

        conn.commit()
        return new_submission_id

    except Exception as e:
        print(f"Erro ao replicar submissão: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_submission_author(submission_id):
    """Retorna o ID do usuário que criou uma submissão."""
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor()
    cursor.execute("SELECT UsuarioID FROM Submissoes WHERE ID = ?", submission_id)
    row = cursor.fetchone()
    conn.close()
    return row.UsuarioID if row else None

def get_submission_for_resubmit(submission_id):
    """Busca os dados de uma submissão para preencher o formulário de reenvio/edição."""
    conn = get_connection()
    if not conn: return None, None

    # Primeiro, busca a estrutura do checklist
    cursor = conn.cursor()
    cursor.execute("SELECT ChecklistID FROM Submissoes WHERE ID = ?", submission_id)
    checklist_id_row = cursor.fetchone()
    if not checklist_id_row:
        conn.close()
        return None, None
    
    checklist_structure = get_flexible_checklist_for_filling(checklist_id_row.ChecklistID)

    # Depois, busca as respostas existentes para esta submissão
    cursor.execute("""
        SELECT r.ComponenteID, r.TipoRespostaID, r.Resposta 
        FROM Respostas r 
        WHERE r.SubmissaoID = ?
    """, submission_id)
    
    existing_answers = {}
    for row in cursor.fetchall():
        if row.ComponenteID not in existing_answers:
            existing_answers[row.ComponenteID] = {}
        existing_answers[row.ComponenteID][row.TipoRespostaID] = row.Resposta

    conn.close()
    return checklist_structure, existing_answers


def get_submission_for_resubmit(submission_id):
    """Busca os dados de uma submissão para preencher o formulário de reenvio/edição."""
    conn = get_connection()
    if not conn: return None, None

    # Primeiro, busca a estrutura do checklist
    cursor = conn.cursor()
    cursor.execute("SELECT ChecklistID FROM Submissoes WHERE ID = ?", submission_id)
    checklist_id_row = cursor.fetchone()
    if not checklist_id_row:
        conn.close()
        return None, None
    
    checklist_structure = get_flexible_checklist_for_filling(checklist_id_row.ChecklistID)

    # Depois, busca as respostas existentes para esta submissão
    cursor.execute("""
        SELECT r.ComponenteID, r.TipoRespostaID, r.Resposta 
        FROM Respostas r 
        WHERE r.SubmissaoID = ?
    """, submission_id)
    
    existing_answers = {}
    for row in cursor.fetchall():
        if row.ComponenteID not in existing_answers:
            existing_answers[row.ComponenteID] = {}
        # Armazena a resposta, usando o TipoRespostaID como chave
        if row.TipoRespostaID:
            existing_answers[row.ComponenteID][row.TipoRespostaID] = row.Resposta

    conn.close()
    return checklist_structure, existing_answers

def update_submission_answers(submission_id, user_id, answers, participants):
    """
    Atualiza as respostas de uma submissão existente. Apaga as respostas antigas e salva as novas.
    """
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        # Apaga todas as respostas e fotos antigas desta submissão para evitar duplicatas
        # A exclusão em cascata cuidará da tabela FotosResposta
        cursor.execute("DELETE FROM Respostas WHERE SubmissaoID = ?", submission_id)

        # Atualiza o autor para quem fez a última modificação
        cursor.execute("UPDATE Submissoes SET UsuarioID = ?, NomeTrabalhadorAuditado = ?, NomeResponsavelArea = ? WHERE ID = ?", 
                       user_id, participants['worker_name'], participants['area_manager_name'], submission_id)


        # Reinsere as novas respostas (lógica de save_flexible_checklist_response)
        for component_id, data in answers.items():
            responses = data.get('responses', {})
            observation = data.get('observation')
            is_first_response = True

            for rt_id, answer_value in responses.items():
                obs_to_save = observation if is_first_response else None
                sql_get_id = "SET NOCOUNT ON; INSERT INTO Respostas (SubmissaoID, ComponenteID, TipoRespostaID, Resposta, Observacao) VALUES (?, ?, ?, ?, ?); SELECT SCOPE_IDENTITY();"
                
                if isinstance(answer_value, list):
                    placeholder_text = f"{len(answer_value)} foto(s) anexada(s)"
                    cursor.execute(sql_get_id, submission_id, component_id, rt_id, placeholder_text, obs_to_save)
                    resposta_id = cursor.fetchone()[0]
                    
                    for photo_path in answer_value:
                        cursor.execute("INSERT INTO FotosResposta (RespostaID, CaminhoFoto) VALUES (?, ?)", resposta_id, photo_path)
                else:
                    cursor.execute(sql_get_id, submission_id, component_id, rt_id, answer_value, obs_to_save)
                
                is_first_response = False

        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar respostas: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()