# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from functools import wraps
import database as db
import auth
import json
import os
from werkzeug.utils import secure_filename
import secrets
import string
from itertools import groupby

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# --- CONFIGURAÇÕES ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator_factory(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            roles = [role] if isinstance(role, str) else role
            if session.get('role') not in roles:
                flash("Você não tem permissão para acessar esta página.", "danger")
                return redirect(url_for('dashboard'))
            return view_func(*args, **kwargs)
        return wrapper
    return decorator_factory

# --- FUNÇÕES AUXILIARES ---

# Em app.py, substitua a função calculate_audit_score

def calculate_audit_score(submission_items):
    """
    Calcula o placar de conformidade, separando itens aplicáveis de não aplicáveis.
    """
    # Define quais respostas contam para o placar e quais são neutras
    auditable_answers = ['Conforme', 'Não Conforme', 'Bom', 'Ruim']
    neutral_answers = ['Não se Aplica', 'N/A']
    
    auditable_items = []
    not_applicable_items = 0

    for item in submission_items:
        answer_value = item.get('valor')
        # Se a resposta for de auditoria (Conforme/Não Conforme), adiciona à lista de cálculo
        if answer_value in auditable_answers and item.get('is_conforme') is not None:
            auditable_items.append(item)
        # Se a resposta for neutra, apenas incrementa o contador
        elif answer_value in neutral_answers:
            not_applicable_items += 1

    total_auditable = len(auditable_items)
    
    # Se não houver itens de auditoria, mas houver itens "N/A", retorna um placar zerado
    if total_auditable == 0:
        if not_applicable_items > 0:
             return {'total': 0, 'compliant': 0, 'flagged': 0, 'percentage': 100, 'not_applicable': not_applicable_items}
        else:
            return None # Não há nada para pontuar

    compliant_items = sum(1 for item in auditable_items if item.get('is_conforme'))
    
    score = {
        'total': total_auditable,
        'compliant': compliant_items,
        'flagged': total_auditable - compliant_items,
        'percentage': (compliant_items / total_auditable) * 100 if total_auditable > 0 else 0,
        'not_applicable': not_applicable_items # Nova informação
    }
    return score

def convert_checklist_to_dict(checklist_data):
    if not checklist_data: return None
    def component_to_dict(c):
        data_dict = {
            'ID': c['data'].ID, 'TextoComponente': c['data'].TextoComponente,
            'TipoComponente': c['data'].TipoComponente, 'Instrucao': c['data'].Instrucao,
            'ParentID': c['data'].ParentID
        }
        if hasattr(c['data'], 'Titulo'): data_dict['Titulo'] = c['data'].Titulo
        if hasattr(c['data'], 'SetorID'): data_dict['SetorID'] = c['data'].SetorID
        return {
            'data': data_dict,
            'response_types': [{'details': {'ID': rt['details'].ID}} for rt in c['response_types']],
            'children': [component_to_dict(child) for child in c['children']]
        }
    return {
        'data': {'ID': checklist_data['ID'], 'Titulo': checklist_data['Titulo'], 'SetorID': checklist_data.get('SetorID')},
        'components': [component_to_dict(c) for c in checklist_data['Componentes']]
    }

# --- ROTAS PRINCIPAIS E DE LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        user_data = db.get_user_by_username(username)
        if user_data and auth.verify_password(user_data.SenhaHash, password):
            session['user_id'], session['username'], session['role'] = user_data.ID, user_data.NomeUsuario, user_data.Papel
            session['coordinator_id'] = user_data.ID if user_data.Papel in ['COORDENADOR', 'GESTOR'] else user_data.CoordenadorID
            flash(f"Login bem-sucedido! Bem-vindo(a), {user_data.NomeUsuario}.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Usuário ou senha inválidos.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    role, user_id = session.get('role'), session['user_id']
    if role in ['COORDENADOR', 'GESTOR']:
        return render_template('coordenador_dashboard.html', 
                               collaborators=db.get_collaborators_for_coordinator(user_id), 
                               sectors=db.get_sectors_for_coordinator(user_id))
    elif role == 'COLABORADOR':
        return render_template('colaborador_dashboard.html', 
                               checklists=db.get_checklists_for_collaborator(user_id), 
                               submitted_checklists=db.get_submissions_for_collaborator(user_id))
    else:
        flash("Papel de usuário não reconhecido.", "danger")
        return redirect(url_for('login'))

@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- ROTAS DE GERENCIAMENTO (COORDENADOR/GESTOR) ---
@app.route('/create_user', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def create_user():
    if request.method == 'POST':
        username, password, role = request.form.get('username'), request.form.get('password'), request.form.get('role')
        if not username or not password: flash("Nome de usuário e senha são obrigatórios.", "warning")
        else:
            password_hash = auth.hash_password(password)
            coordinator_id = session['user_id'] if role == 'COLABORADOR' else None
            if db.create_user(username, password_hash, role, coordinator_id):
                flash(f"Usuário '{username}' criado com sucesso!", "success")
                return redirect(url_for('dashboard'))
            else: flash("Erro ao criar usuário. O nome pode já existir.", "danger")
    return render_template('create_user.html')

@app.route('/manage_users')
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def manage_users():
    return render_template('manage_users.html', users=db.get_manageable_users(session['user_id']))

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def edit_user(user_id):
    if request.method == 'POST':
        username, role, coordinator_id = request.form.get('username'), request.form.get('role'), request.form.get('coordinator_id')
        if role in ['COORDENADOR', 'GESTOR']: coordinator_id = None
        if not username or not role: flash("Nome de usuário e Papel são obrigatórios.", "warning")
        else:
            if db.update_user_info(user_id, username, role, coordinator_id):
                flash("Usuário atualizado com sucesso!", "success")
                return redirect(url_for('manage_users'))
            else: flash("Erro ao atualizar usuário. O nome pode já existir.", "danger")
        return redirect(url_for('edit_user', user_id=user_id))
    user = db.get_user_by_id(user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('manage_users'))
    return render_template('edit_user.html', user=user, coordinators=db.get_all_coordinators())

@app.route('/reset_password/<int:user_id>', methods=['POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def reset_password(user_id):
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for _ in range(10))
    if db.update_user_password(user_id, auth.hash_password(new_password)):
        flash(f"Senha redefinida! Nova senha: {new_password}", "success")
    else: flash("Erro ao resetar a senha.", "danger")
    return redirect(url_for('manage_users'))

@app.route('/create_flexible_checklist', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def create_flexible_checklist():
    if request.method == 'POST':
        title, sector_id, components_json = request.form.get('title'), request.form.get('sector_id'), request.form.get('components_data')
        if not all([title, sector_id, components_json]): flash("Título, setor e componentes são obrigatórios.", "warning")
        else:
            try:
                if db.create_flexible_checklist(title, sector_id, json.loads(components_json)):
                    flash(f"Checklist '{title}' criado com sucesso!", "success")
                    return redirect(url_for('manage_checklists'))
                else: flash("Ocorreu um erro ao criar o checklist.", "danger")
            except Exception as e: flash(f"Erro ao processar os dados: {e}", "danger")
    return render_template('checklist_form.html', sectors=db.get_sectors_for_coordinator(session['user_id']), response_types=db.get_all_response_types())

@app.route('/edit_checklist/<int:checklist_id>', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def edit_checklist(checklist_id):
    if request.method == 'POST':
        title, sector_id, components_json = request.form.get('title'), request.form.get('sector_id'), request.form.get('components_data')
        if not all([title, sector_id, components_json]):
            flash("Todos os campos são obrigatórios.", "danger")
        else:
            if db.update_flexible_checklist(checklist_id, title, sector_id, json.loads(components_json)):
                flash("Checklist atualizado com sucesso!", "success")
                return redirect(url_for('manage_checklists'))
            else: flash("Erro ao atualizar o checklist.", "danger")
        return redirect(url_for('edit_checklist', checklist_id=checklist_id))
    checklist_data = db.get_checklist_for_editing(checklist_id)
    if not checklist_data:
        flash("Checklist não encontrado.", "danger")
        return redirect(url_for('manage_checklists'))
    return render_template('checklist_form.html', checklist=convert_checklist_to_dict(checklist_data), checklist_json=json.dumps(convert_checklist_to_dict(checklist_data)), sectors=db.get_sectors_for_coordinator(session['user_id']), response_types=db.get_all_response_types())

@app.route('/manage_checklists')
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def manage_checklists():
    return render_template('manage_checklists.html', checklists=db.get_checklists_for_coordinator(session['user_id']))

@app.route('/delete_checklist/<int:checklist_id>', methods=['POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def delete_checklist(checklist_id):
    success, message = db.delete_checklist(checklist_id)
    flash(message, "success" if success else "danger")
    return redirect(url_for('manage_checklists'))

@app.route('/view_responses')
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def view_responses():
    return render_template('view_responses.html', submissions=db.get_submissions_for_coordinator(session['user_id']))

@app.route('/delete_submission/<int:submission_id>', methods=['POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def delete_submission(submission_id):
    if db.delete_submission(submission_id): flash("A resposta do checklist foi apagada com sucesso.", "success")
    else: flash("Ocorreu um erro ao tentar apagar a resposta.", "danger")
    return redirect(url_for('view_responses'))

@app.route('/edit_submission/<int:submission_id>', methods=['POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR', 'COLABORADOR'])
def edit_submission(submission_id):
    author_id = db.get_submission_author(submission_id)
    if session['role'] == 'COLABORADOR' and session['user_id'] != author_id:
        flash("Você só pode editar os checklists que você mesmo enviou.", "danger")
        return redirect(url_for('dashboard'))
    new_id = db.replicate_submission_for_editing(submission_id, session['user_id'])
    if new_id:
        flash("Uma nova versão editável foi criada. O original foi arquivado.", "info")
        return redirect(url_for('resubmit_checklist', submission_id=new_id))
    else:
        flash("Erro ao criar uma nova versão do checklist.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/submission/<int:submission_id>')
@login_required
def submission_details(submission_id):
    submission_data = db.get_submission_details(submission_id)
    if not submission_data:
        flash("Resposta não encontrada.", "danger")
        return redirect(url_for('dashboard'))
    is_coordinator = session['role'] in ['COORDENADOR', 'GESTOR']
    is_author = (session['role'] == 'COLABORADOR' and submission_data['header'].UsuarioID == session['user_id'])
    if not is_coordinator and not is_author:
        flash("Você não tem permissão para visualizar esta resposta.", "danger")
        return redirect(url_for('dashboard'))
    all_answers = [ans for comp in submission_data['details'] for ans in comp['answers']]
    for comp in submission_data['details']:
        for child in comp['children']: all_answers.extend(child['answers'])
    return render_template('submission_details.html', submission=submission_data, audit_score=calculate_audit_score(all_answers))

@app.route('/reports', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def reports():
    coordinator_id, report_data, filters, report_scores = session['user_id'], [], {}, {}
    if request.method == 'POST':
        filters = {k: request.form.get(k) for k in ['checklist_id', 'user_id', 'start_date', 'end_date', 'question', 'answer']}
        report_data_db = db.get_filtered_submissions(coordinator_id, **{k: v or None for k, v in filters.items()})
        if report_data_db:
            report_data = [dict(row) for row in report_data_db]
            for row in report_data:
                row['photo_list'] = row['CaminhosFotos'].split(',') if row.get('CaminhosFotos') else []
            for sub_id, group in groupby(report_data, key=lambda x: x['SubmissaoID']):
                report_scores[sub_id] = calculate_audit_score(list(group))
    return render_template('reports.html', checklists=db.get_checklists_for_coordinator(coordinator_id), users=db.get_manageable_users(coordinator_id), questions=db.get_all_distinct_questions(coordinator_id), report_data=report_data, filters=filters, report_scores=report_scores)

@app.route('/manage_sectors', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def manage_sectors():
    coordinator_id = session['user_id']
    if request.method == 'POST':
        selected_ids = [int(id) for id in request.form.getlist('sector_ids')]
        if db.update_coordinator_sectors(coordinator_id, selected_ids): flash("Seus setores foram atualizados com sucesso!", "success")
        else: flash("Ocorreu um erro ao atualizar seus setores.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('manage_sectors.html', all_sectors=db.get_all_sectors(), my_sector_ids=[s.ID for s in db.get_sectors_for_coordinator(coordinator_id)])

@app.route('/create_sector', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def create_sector():
    if request.method == 'POST':
        sector_name = request.form.get('sector_name')
        if not sector_name: flash("O nome do setor é obrigatório.", "warning")
        else:
            if db.create_sector(sector_name):
                flash(f"Setor '{sector_name}' criado com sucesso!", "success")
                return redirect(url_for('dashboard'))
            else: flash("Erro ao criar setor. Ele já pode existir.", "danger")
    return render_template('create_sector.html')

@app.route('/manage_response_types', methods=['GET'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def manage_response_types():
    return render_template('manage_response_types.html', response_types=db.get_all_response_types())

@app.route('/create_response_type', methods=['POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def create_response_type():
    name = request.form.get('name')
    options = [opt.strip() for opt in request.form.getlist('options[]') if opt.strip()]
    if not name or len(options) < 2: flash("O nome e pelo menos duas opções são obrigatórios.", "danger")
    else:
        if db.create_response_type(name, options): flash("Novo tipo de resposta criado com sucesso!", "success")
        else: flash("Erro ao criar o tipo de resposta. O nome já pode existir.", "danger")
    return redirect(url_for('manage_response_types'))

@app.route('/delete_response_type/<int:type_id>', methods=['POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def delete_response_type(type_id):
    if db.delete_response_type(type_id): flash("Tipo de resposta deletado com sucesso.", "success")
    else: flash("Erro ao deletar o tipo de resposta.", "danger")
    return redirect(url_for('manage_response_types'))

@app.route('/edit_response_type/<int:type_id>', methods=['GET', 'POST'])
@login_required
@role_required(['COORDENADOR', 'GESTOR'])
def edit_response_type(type_id):
    if request.method == 'POST':
        name, option_texts, conforme_index = request.form.get('name'), request.form.getlist('options_text[]'), request.form.get('is_conforme_radio')
        options = [{'text': text.strip(), 'is_conforme': str(i) == conforme_index} for i, text in enumerate(option_texts) if text.strip()]
        if not name or len(options) < 2: flash("O nome e pelo menos duas opções são obrigatórios.", "danger")
        else:
            if db.update_response_type(type_id, name, options):
                flash("Tipo de resposta atualizado com sucesso!", "success")
                return redirect(url_for('manage_response_types'))
            else: flash("Erro ao atualizar o tipo de resposta.", "danger")
        return redirect(url_for('edit_response_type', type_id=type_id))
    response_type_data = db.get_response_type_by_id(type_id)
    if not response_type_data:
        flash("Tipo de resposta não encontrado.", "danger")
        return redirect(url_for('manage_response_types'))
    return render_template('edit_response_type.html', response_type=response_type_data)

# --- ROTAS DE PREENCHIMENTO (COLABORADOR) ---
@app.route('/fill_checklist/<int:checklist_id>', methods=['GET', 'POST'])
@login_required
@role_required('COLABORADOR')
def fill_checklist(checklist_id):
    if request.method == 'POST':
        participants = {'worker_name': request.form.get('worker_name'), 'area_manager_name': request.form.get('area_manager_name')}
        answers = {}
        def ensure_comp_struct(comp_id):
            if comp_id not in answers: answers[comp_id] = {'responses': {}, 'observation': None}
        for key, value in request.form.items():
            if key.startswith('answer_'):
                parts = key.split('_'); component_id, rt_id = int(parts[1]), int(parts[2])
                ensure_comp_struct(component_id); answers[component_id]['responses'][rt_id] = value.strip()
            elif key.startswith('observation_'):
                component_id = int(key.split('_')[1])
                ensure_comp_struct(component_id); answers[component_id]['observation'] = value.strip()
        for key in request.files:
            if key.startswith('answer_'):
                files_list = request.files.getlist(key)
                if not files_list or not files_list[0].filename: continue
                parts = key.split('_'); component_id, rt_id = int(parts[1]), int(parts[2])
                ensure_comp_struct(component_id)
                photo_paths = []
                for file in files_list:
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{session['user_id']}_{component_id}_{rt_id}_{secrets.token_hex(4)}_{filename}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        file.save(file_path); photo_paths.append(unique_filename)
                if photo_paths: answers[component_id]['responses'][rt_id] = photo_paths
        if not answers:
            flash("Nenhuma resposta foi enviada.", "warning")
            return redirect(url_for('fill_checklist', checklist_id=checklist_id))
        if db.save_flexible_checklist_response(checklist_id, session['user_id'], answers, participants):
            flash("Checklist respondido com sucesso!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Erro ao salvar o checklist.", "danger")
            return redirect(url_for('fill_checklist', checklist_id=checklist_id))
    checklist_data = db.get_flexible_checklist_for_filling(checklist_id)
    if not checklist_data:
        flash("Checklist não encontrado.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('fill_checklist.html', checklist=checklist_data)

@app.route('/resubmit_checklist/<int:submission_id>', methods=['GET'])
@login_required
def resubmit_checklist(submission_id):
    checklist_structure, existing_answers = db.get_submission_for_resubmit(submission_id)
    if not checklist_structure:
        flash("Checklist para reenvio não encontrado.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('fill_checklist.html', checklist=checklist_structure, existing_answers=existing_answers, is_resubmit=True, submission_id=submission_id)

@app.route('/save_resubmission/<int:submission_id>', methods=['POST'])
@login_required
def save_resubmission(submission_id):
    participants = {'worker_name': request.form.get('worker_name'), 'area_manager_name': request.form.get('area_manager_name')}
    answers = {}
    def ensure_comp_struct(comp_id):
        if comp_id not in answers: answers[comp_id] = {'responses': {}, 'observation': None}
    for key, value in request.form.items():
        if key.startswith('answer_'):
            parts = key.split('_'); component_id, rt_id = int(parts[1]), int(parts[2])
            ensure_comp_struct(component_id); answers[component_id]['responses'][rt_id] = value.strip()
        elif key.startswith('observation_'):
            component_id = int(key.split('_')[1])
            ensure_comp_struct(component_id); answers[component_id]['observation'] = value.strip()
    for key in request.files:
        if key.startswith('answer_'):
            files_list = request.files.getlist(key)
            if not files_list or not files_list[0].filename: continue
            parts = key.split('_'); component_id, rt_id = int(parts[1]), int(parts[2])
            ensure_comp_struct(component_id)
            photo_paths = []
            for file in files_list:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{session['user_id']}_{component_id}_{rt_id}_{secrets.token_hex(4)}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path); photo_paths.append(unique_filename)
            if photo_paths: answers[component_id]['responses'][rt_id] = photo_paths
    if db.update_submission_answers(submission_id, session['user_id'], answers, participants):
        flash("Checklist atualizado com sucesso!", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Erro ao salvar as alterações do checklist.", "danger")
        return redirect(url_for('resubmit_checklist', submission_id=submission_id))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)