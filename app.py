from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '1112223333'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://bars:7AJTm2ZafCE8FdV8GtPWBWHz0CmaDlg8@dpg-d48curjipnbc73de2jh0-a/quiz_db_y51y'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    quizzes = Quiz.query.all()  # Убрана фильтрация по is_active
    return render_template('index.html', quizzes=quizzes)


@app.route('/quiz/<int:quiz_id>/start')
def start_quiz(quiz_id):
    """Начало квиза (новая страница с пошаговым прохождением)"""
    quiz = Quiz.query.get_or_404(quiz_id)
    # Сортируем вопросы по order_index
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

        # Собираем ответы из формы
        for key, value in request.form.items():
            if key.startswith('question_'):
                question_id = int(key.replace('question_', ''))
                answer_id = int(value)

                # Проверяем, что ответ существует и принадлежит вопросу
                answer = Answer.query.filter_by(id=answer_id, question_id=question_id).first()
                if answer:
                    total_score += answer.score
                    answered_questions.add(question_id)

        # Проверяем, что ответили на все вопросы
        quiz_questions_count = Question.query.filter_by(quiz_id=quiz_id).count()
        if len(answered_questions) != quiz_questions_count:
            flash('Пожалуйста, ответьте на все вопросы!', 'error')
            return redirect(url_for('start_quiz', quiz_id=quiz_id))

        # Ищем подходящий результат
        result = Result.query.filter(
            Result.quiz_id == quiz_id,
            Result.min_score <= total_score,
            Result.max_score >= total_score
        ).first()

        if not result:
            # Если результат не найден, берем ближайший по баллам
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


# АДМИН-МАРШРУТЫ
@app.route('/admin')
def admin_dashboard():
    """Админ-панель - список всех квизов"""
    quizzes = Quiz.query.all()
    return render_template('admin.html', quizzes=quizzes)


@app.route('/admin/quiz/new', methods=['GET', 'POST'])
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
def admin_edit_quiz(quiz_id):
    """Редактирование квиза"""
    quiz = Quiz.query.get_or_404(quiz_id)

    if request.method == 'POST':
        try:
            quiz.title = request.form.get('title')
            quiz.description = request.form.get('description')
            # Убрана логика is_active

            db.session.commit()
            flash('Квиз успешно обновлен!', 'success')
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении квиза: {str(e)}', 'error')

    return render_template('admin_quiz_form.html', quiz=quiz)


@app.route('/admin/quiz/<int:quiz_id>/delete', methods=['POST'])
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
def admin_quiz_questions(quiz_id):
    """Управление вопросами квиза"""
    quiz = Quiz.query.get_or_404(quiz_id)
    return render_template('admin_questions.html', quiz=quiz)


@app.route('/admin/question/<int:question_id>/edit', methods=['GET', 'POST'])
def admin_edit_question(question_id):
    """Редактирование вопроса"""
    question = Question.query.get_or_404(question_id)

    if request.method == 'POST':
        try:
            question.text = request.form.get('text')
            question.order_index = int(request.form.get('order_index', 0))

            # Обновляем ответы
            answer_texts = request.form.getlist('answer_text[]')
            answer_scores = request.form.getlist('answer_score[]')

            # Удаляем старые ответы
            Answer.query.filter_by(question_id=question.id).delete()

            # Добавляем новые ответы
            for i in range(len(answer_texts)):
                if answer_texts[i].strip():  # Проверяем, что текст ответа не пустой
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

            # Добавляем ответы
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
def admin_quiz_results(quiz_id):
    """Управление результатами квиза"""
    quiz = Quiz.query.get_or_404(quiz_id)
    return render_template('admin_results.html', quiz=quiz)


@app.route('/admin/result/<int:result_id>/edit', methods=['GET', 'POST'])
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


# Утилиты
@app.route('/create-sample-data')
def create_sample_data():
    """Маршрут для создания тестовых данных (для разработки)"""
    try:
        # Очищаем существующие данные
        db.drop_all()
        db.create_all()

        # 1. Создаем квиз
        quiz1 = Quiz(
            title="Какой вы тип маркетолога?",
            description="Пройдите тест и узнайте, какой у вас тип маркетингового мышления",
            created_at=datetime.utcnow()
        )
        db.session.add(quiz1)
        db.session.flush()

        # 2. Добавляем вопросы
        questions_data = [
            {
                'text': 'Как вы подходите к планированию маркетинговой кампании?',
                'order_index': 1,
                'answers': [
                    {'text': 'Тщательно анализирую данные и составляю детальный план', 'score': 5},
                    {'text': 'Создаю общую стратегию, детали решаю по ходу', 'score': 3},
                    {'text': 'Действую интуитивно, импровизирую', 'score': 1},
                    {'text': 'Копирую успешные кейсы конкурентов', 'score': 2}
                ]
            },
            {
                'text': 'Что для вас важнее в рекламном креативе?',
                'order_index': 2,
                'answers': [
                    {'text': 'Креативность и оригинальность', 'score': 1},
                    {'text': 'Измеримость результатов', 'score': 5},
                    {'text': 'Вирусный потенциал', 'score': 3},
                    {'text': 'Соответствие бренду', 'score': 4}
                ]
            }
        ]

        for q_data in questions_data:
            question = Question(
                quiz_id=quiz1.id,
                text=q_data['text'],
                order_index=q_data['order_index']
            )
            db.session.add(question)
            db.session.flush()

            for a_data in q_data['answers']:
                answer = Answer(
                    question_id=question.id,
                    text=a_data['text'],
                    score=a_data['score']
                )
                db.session.add(answer)

        # 3. Добавляем результаты
        results_data = [
            {
                'min_score': 6,
                'max_score': 10,
                'title': '📊 Аналитик',
                'description': 'Вы - прирожденный аналитик!',
                'image_url': '/static/images/analyst.png'
            },
            {
                'min_score': 3,
                'max_score': 5,
                'title': '🎨 Креативщик',
                'description': 'Вы - творческая личность!',
                'image_url': '/static/images/creative.png'
            }
        ]

        for r_data in results_data:
            result = Result(
                quiz_id=quiz1.id,
                min_score=r_data['min_score'],
                max_score=r_data['max_score'],
                title=r_data['title'],
                description=r_data['description'],
                image_url=r_data['image_url']
            )
            db.session.add(result)

        db.session.commit()
        flash('Тестовые данные успешно созданы!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при создании тестовых данных: {str(e)}', 'error')

    return redirect(url_for('admin_dashboard'))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)