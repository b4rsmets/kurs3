import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import ssl
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '1112223333')

# Строка подключения
database_url = 'postgresql+pg8000://bars:V5QrN0YBAahV7fXVUGUAxLWp0oziEcAi@dpg-d4u62oq4d50c739hb1dg-a.frankfurt-postgres.render.com:5432/quiz_db_bew6'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Исправленная конфигурация SSL для pg8000
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'ssl_context': ssl_context
    }
}

db = SQLAlchemy(app)

ADMIN_CREDENTIALS = {
    'username': 'admin',
    'password': 'admin123'
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)

    return decorated_function


class Quiz(db.Model):
    __tablename__ = 'quiz'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade='all, delete-orphan')
    results = db.relationship('Result', backref='quiz', lazy=True, cascade='all, delete-orphan')


class Question(db.Model):
    __tablename__ = 'question'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, default=0)
    answers = db.relationship('Answer', backref='question', lazy=True, cascade='all, delete-orphan')


class Answer(db.Model):
    __tablename__ = 'answer'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    score = db.Column(db.Integer, nullable=False)


class Result(db.Model):
    __tablename__ = 'result'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    min_score = db.Column(db.Integer, nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))


@app.route('/')
def index():
    """Главная страница со списком квизов"""
    quizzes = Quiz.query.all()
    return render_template('index.html', quizzes=quizzes)


@app.route('/quiz/<int:quiz_id>/start')
def start_quiz(quiz_id):
    """Начало квиза"""
    quiz = Quiz.query.get_or_404(quiz_id)
    quiz.questions = sorted(quiz.questions, key=lambda x: x.order_index)
    return render_template('quiz.html', quiz=quiz)


@app.route('/quiz/<int:quiz_id>')
def show_quiz(quiz_id):
    """Старая версия - редирект на новую"""
    return redirect(url_for('start_quiz', quiz_id=quiz_id))


@app.route('/quiz/<int:quiz_id>/submit', methods=['POST'])
def submit_quiz(quiz_id):
    """Обработка ответов и вывод результата"""
    try:
        total_score = 0
        answered_questions = set()

        for key, value in request.form.items():
            if key.startswith('question_'):
                question_id = int(key.replace('question_', ''))
                answer_id = int(value)
                answer = Answer.query.filter_by(id=answer_id, question_id=question_id).first()
                if answer:
                    total_score += answer.score
                    answered_questions.add(question_id)

        quiz_questions_count = Question.query.filter_by(quiz_id=quiz_id).count()
        if len(answered_questions) != quiz_questions_count:
            flash('Пожалуйста, ответьте на все вопросы!', 'error')
            return redirect(url_for('start_quiz', quiz_id=quiz_id))

        result = Result.query.filter(
            Result.quiz_id == quiz_id,
            Result.min_score <= total_score,
            Result.max_score >= total_score
        ).first()

        if not result:
            results = Result.query.filter_by(quiz_id=quiz_id).all()
            if results:
                result = min(results, key=lambda x: abs((x.min_score + x.max_score) / 2 - total_score))
            else:
                flash('Результат не найден. Пожалуйста, попробуйте еще раз.', 'error')
                return redirect(url_for('start_quiz', quiz_id=quiz_id))

        return render_template('result.html', result=result, score=total_score, quiz_id=quiz_id)

    except Exception as e:
        flash(f'Произошла ошибка: {str(e)}', 'error')
        return redirect(url_for('start_quiz', quiz_id=quiz_id))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Страница входа для администратора"""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
            session['admin_logged_in'] = True
            flash('Успешный вход в админ-панель!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')

    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """Выход из админ-панели"""
    session.pop('admin_logged_in', None)
    flash('Вы вышли из админ-панели', 'success')
    return redirect(url_for('admin_login'))


@app.route('/admin')
@login_required
def admin_dashboard():
    """Админ-панель - список всех квизов"""
    quizzes = Quiz.query.all()
    return render_template('admin.html', quizzes=quizzes)


@app.route('/admin/quiz/new', methods=['GET', 'POST'])
@login_required
def admin_create_quiz():
    """Создание нового квиза"""
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            description = request.form.get('description')

            if not title:
                flash('Название квиза обязательно', 'error')
                return redirect(url_for('admin_create_quiz'))

            quiz = Quiz(title=title, description=description)
            db.session.add(quiz)
            db.session.commit()

            flash('Квиз успешно создан! Теперь добавьте вопросы и ответы.', 'success')
            return redirect(url_for('admin_edit_quiz', quiz_id=quiz.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании квиза: {str(e)}', 'error')

    return render_template('admin_quiz_form.html', quiz=None)


@app.route('/admin/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_quiz(quiz_id):
    """Редактирование квиза"""
    quiz = Quiz.query.get_or_404(quiz_id)

    if request.method == 'POST':
        try:
            quiz.title = request.form.get('title')
            quiz.description = request.form.get('description')

            db.session.commit()
            flash('Квиз успешно обновлен!', 'success')
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении квиза: {str(e)}', 'error')

    return render_template('admin_quiz_form.html', quiz=quiz)


@app.route('/admin/quiz/<int:quiz_id>/delete', methods=['POST'])
@login_required
def admin_delete_quiz(quiz_id):
    """Удаление квиза"""
    try:
        quiz = Quiz.query.get_or_404(quiz_id)
        db.session.delete(quiz)
        db.session.commit()
        flash('Квиз успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении квиза: {str(e)}', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/quiz/<int:quiz_id>/questions')
@login_required
def admin_quiz_questions(quiz_id):
    """Управление вопросами квиза"""
    quiz = Quiz.query.get_or_404(quiz_id)
    return render_template('admin_questions.html', quiz=quiz)


@app.route('/admin/question/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_question(question_id):
    """Редактирование вопроса"""
    question = Question.query.get_or_404(question_id)

    if request.method == 'POST':
        try:
            question.text = request.form.get('text')
            question.order_index = int(request.form.get('order_index', 0))

            answer_texts = request.form.getlist('answer_text[]')
            answer_scores = request.form.getlist('answer_score[]')

            Answer.query.filter_by(question_id=question.id).delete()

            for i in range(len(answer_texts)):
                if answer_texts[i].strip():
                    answer = Answer(
                        question_id=question.id,
                        text=answer_texts[i].strip(),
                        score=int(answer_scores[i])
                    )
                    db.session.add(answer)

            db.session.commit()
            flash('Вопрос успешно обновлен!', 'success')
            return redirect(url_for('admin_quiz_questions', quiz_id=question.quiz_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении вопроса: {str(e)}', 'error')

    return render_template('admin_question_form.html', question=question)


@app.route('/admin/quiz/<int:quiz_id>/question/new', methods=['GET', 'POST'])
@login_required
def admin_create_question(quiz_id):
    """Создание нового вопроса"""
    quiz = Quiz.query.get_or_404(quiz_id)

    if request.method == 'POST':
        try:
            text = request.form.get('text')
            order_index = int(request.form.get('order_index', 0))

            if not text:
                flash('Текст вопроса обязателен', 'error')
                return redirect(url_for('admin_create_question', quiz_id=quiz_id))

            question = Question(
                quiz_id=quiz_id,
                text=text,
                order_index=order_index
            )
            db.session.add(question)
            db.session.flush()

            answer_texts = request.form.getlist('answer_text[]')
            answer_scores = request.form.getlist('answer_score[]')

            for i in range(len(answer_texts)):
                if answer_texts[i].strip():
                    answer = Answer(
                        question_id=question.id,
                        text=answer_texts[i].strip(),
                        score=int(answer_scores[i])
                    )
                    db.session.add(answer)

            db.session.commit()
            flash('Вопрос успешно создан!', 'success')
            return redirect(url_for('admin_quiz_questions', quiz_id=quiz_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании вопроса: {str(e)}', 'error')

    return render_template('admin_question_form.html', question=None, quiz=quiz)


@app.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@login_required
def admin_delete_question(question_id):
    """Удаление вопроса"""
    try:
        question = Question.query.get_or_404(question_id)
        quiz_id = question.quiz_id
        db.session.delete(question)
        db.session.commit()
        flash('Вопрос успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении вопроса: {str(e)}', 'error')

    return redirect(url_for('admin_quiz_questions', quiz_id=quiz_id))


@app.route('/admin/quiz/<int:quiz_id>/results')
@login_required
def admin_quiz_results(quiz_id):
    """Управление результатами квиза"""
    quiz = Quiz.query.get_or_404(quiz_id)
    return render_template('admin_results.html', quiz=quiz)


@app.route('/admin/result/<int:result_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_result(result_id):
    """Редактирование результата"""
    result = Result.query.get_or_404(result_id)

    if request.method == 'POST':
        try:
            result.title = request.form.get('title')
            result.description = request.form.get('description')
            result.min_score = int(request.form.get('min_score'))
            result.max_score = int(request.form.get('max_score'))
            result.image_url = request.form.get('image_url')

            db.session.commit()
            flash('Результат успешно обновлен!', 'success')
            return redirect(url_for('admin_quiz_results', quiz_id=result.quiz_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении результата: {str(e)}', 'error')

    return render_template('admin_result_form.html', result=result)


@app.route('/admin/quiz/<int:quiz_id>/result/new', methods=['GET', 'POST'])
@login_required
def admin_create_result(quiz_id):
    """Создание нового результата"""
    quiz = Quiz.query.get_or_404(quiz_id)

    if request.method == 'POST':
        try:
            title = request.form.get('title')
            description = request.form.get('description')
            min_score = int(request.form.get('min_score'))
            max_score = int(request.form.get('max_score'))
            image_url = request.form.get('image_url')

            if not title:
                flash('Название результата обязательно', 'error')
                return redirect(url_for('admin_create_result', quiz_id=quiz_id))

            result = Result(
                quiz_id=quiz_id,
                title=title,
                description=description,
                min_score=min_score,
                max_score=max_score,
                image_url=image_url
            )
            db.session.add(result)
            db.session.commit()

            flash('Результат успешно создан!', 'success')
            return redirect(url_for('admin_quiz_results', quiz_id=quiz_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании результата: {str(e)}', 'error')

    return render_template('admin_result_form.html', result=None, quiz=quiz)


@app.route('/admin/result/<int:result_id>/delete', methods=['POST'])
@login_required
def admin_delete_result(result_id):
    """Удаление результата"""
    try:
        result = Result.query.get_or_404(result_id)
        quiz_id = result.quiz_id
        db.session.delete(result)
        db.session.commit()
        flash('Результат успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении результата: {str(e)}', 'error')

    return redirect(url_for('admin_quiz_results', quiz_id=quiz_id))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


def create_tables():
    """Функция для создания таблиц"""
    try:
        with app.app_context():
            db.create_all()
            print("✅ Таблицы успешно созданы или уже существуют")
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")


if __name__ == '__main__':
    # Создаем таблицы при запуске
    create_tables()
    # Для локального запуска
    app.run(debug=True, host='0.0.0.0', port=5000)