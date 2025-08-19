from django.shortcuts import render, redirect
from django.views import generic
from django.template import Template, Context
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.utils import timezone
from sympy import sympify, N, Symbol
from collections import defaultdict
from django.db.models import Count

from .models import Category, Issue, Task, UsedVariable, AnswerOption, AdditionalVariable, Variable, UserAnswer, Solution, TaskLevel
from .forms import RegisterForm

import numpy as np
import random

from django.template import Template, Context

def prime_factorization(number):
    """Returns the prime factorization of a number as a list."""
    factors = []
    divisor = 2
    while number > 1:
        while number % divisor == 0:
            factors.append(divisor)
            number //= divisor
        divisor += 1
    return factors

def simplify_square_root(factor):
    """Simplifies the square root of a factor."""

    if factor == 0:
        return "0"
    elif factor == 1:
        return "1"
    
    factors = prime_factorization(factor)
    unique_factors = set(factors)
    
    simplified = 1
    for f in unique_factors:
        count = factors.count(f)
        if count % 2 == 0:
            simplified *= f ** (count // 2)
        else:
            simplified *= f ** ((count - 1) // 2)
    
    return f"{simplified} * sqrt({factor // (simplified ** 2)})" if simplified != 1 else f"sqrt({factor})"


class RegisterView(generic.CreateView):
    form_class = RegisterForm
    template_name = 'matematyka/register.html'
    
    def form_valid(self, form):
        user = form.save()
        default_group, created = Group.objects.get_or_create(name='Uzytkownicy')
        user.groups.add(default_group)
        if user:
            login(self.request, user)

        return redirect('category_list')

class CategoryListView(generic.ListView):
    """
    Displaying a list of math problem categories.
    For each category included in the context of assigned tasks ("task_count"),
    allowing you to see, for example, how many tasks a given category contains.
    """

    model = Category
    template_name = 'matematyka/categories.html'
    context_object_name = 'categories'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for category in context['categories']:
            category.task_count = category.tasks.count()
        return context
    
class CategoryTasksView(generic.DetailView):
    model = Category
    template_name = 'matematyka/category_tasks.html'
    context_object_name = 'category'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        request.session['origin'] = {
            'type': 'category',
            'id': self.object.id
        }
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_tasks = self.object.tasks.all()
        
        issues = Issue.objects.filter(task__category=self.object)
        
        user = self.request.user if self.request.user.is_authenticated else None
        user_answers = UserAnswer.objects.filter(
            issue__in=issues,
            user=user
        ).select_related('issue', 'issue__task').prefetch_related('answer_options')
        
        total_attempts_original = defaultdict(int)
        correct_attempts_original = defaultdict(int)
        total_attempts_random = defaultdict(int)
        correct_attempts_random = defaultdict(int)        
        for ua in user_answers:
            answer_option = ua.answer_options.first()
            if answer_option:
                if ua.issue.variable_is_random:
                    total_attempts_random[ua.issue.task_id] += 1
                    if answer_option.is_correct:
                        correct_attempts_random[ua.issue.task_id] += 1
                else:
                    total_attempts_original[ua.issue.task_id] += 1
                    if answer_option.is_correct:
                        correct_attempts_original[ua.issue.task_id] += 1

        tasks = []
        for task in category_tasks:
            tasks.append({
                'task': task,
                'total_attempts_original': total_attempts_original[task.id],
                'correct_attempts_original': correct_attempts_original[task.id],
                'total_attempts_random': total_attempts_random[task.id],
                'correct_attempts_random': correct_attempts_random[task.id],
            })
            
        context['tasks'] = tasks
        return context
    
class StartIssueView(generic.View):

    def get(self, request, task_id):
        issue = None
        task = Task.objects.get(id=task_id)

        if 'issue_id' in request.session:
            try:
                existing_issue = Issue.objects.get(id=request.session['issue_id'])
                if existing_issue.task.id == task_id:
                    issue = existing_issue
                    variables = list(UsedVariable.objects.filter(issue=issue))
                    value_map = {var.variable_name: var.variable_value for var in variables}
                    answer_options_db = AnswerOption.objects.filter(task=task)
                    symbols = {name: Symbol(name) for name in value_map}
                    substitutions = {
                        symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
                        for k, v in value_map.items()
                    }

                    answer_options = self.build_answer_options(answer_options_db, symbols, value_map, substitutions)
                    
            except Issue.DoesNotExist:
                pass

        if issue is None:
            if self.request.GET.get("random") == "true":
                issue = Issue.objects.create(task=task, variable_is_random=True)
            else:
                issue = Issue.objects.create(task=task, variable_is_random=False)
            request.session['issue_id'] = issue.id

            use_random = request.GET.get("random") == "true"
            if use_random:
                variables = self.randomize_variables(task=task)
            else:
                variables = Variable.objects.filter(task=task)

            additional_variables = AdditionalVariable.objects.filter(task=task)
            answer_options_db = AnswerOption.objects.filter(task=task)

            value_map = {}

            for variable in variables:
                try:
                    value = float(variable.original_value)
                    if value.is_integer():
                        formatted = str(int(value))
                    else:
                        formatted = str(value)
                except ValueError:
                    value = variable.original_value
                    formatted = value

                value_map[variable.name] = formatted

                UsedVariable.objects.create(
                    task=task,
                    issue=issue,
                    variable=variable,
                    variable_name=variable.name,
                    variable_value=str(value)
                )
            
            solutions_map, substitutions = self.build_solutions_map(issue, additional_variables, value_map)
            answer_options = self.build_answer_options(answer_options_db, solutions_map, value_map, substitutions)

        raw_description = task.content
        template = Template(raw_description)
        rendered_description = template.render(Context(value_map))

        context = {
            'issue': issue,
            'variables': value_map,
            'answer_options': answer_options,
            'description': rendered_description
            }
       
        return render(request, 'matematyka/issue.html', context=context)

    def build_solutions_map(self,issue,additional_variables, value_map):
        for add_var in additional_variables:
            expr = sympify(add_var.formula)
            evaluated = expr.subs(value_map)
            print(add_var.name)
            print(expr)
            print(evaluated)
            try:
                numeric_result = round(float(N(evaluated)), 4)
            except TypeError as e:
                raise

            if numeric_result.is_integer():
                formatted = str(int(numeric_result))
            else:
                formatted = str(numeric_result)

            value_map[add_var.name] = formatted
        
            UsedVariable.objects.create(
                task=issue.task,
                issue=issue,
                variable=None,
                variable_name=add_var.name,
                variable_value=str(numeric_result)
            )

        symbols = {name: Symbol(name) for name in value_map}
        
        substitutions = {
            symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
            for k, v in value_map.items()
        }
        return symbols, substitutions


    def build_answer_options(self, answer_options_db, solutions_map, value_map, substitutions):
        answer_options = []
        print(solutions_map)
        print(value_map)
        for opt in answer_options_db:
            # solution = value_map.get(opt.content)
            
            if opt.display_format == 'symbolic':
                raw_description = opt.content
                template = Template(raw_description)
                content = template.render(Context(value_map))

            elif opt.display_format == 'numeric':
                expr = sympify(opt.content,locals=solutions_map)
                content = expr.evalf(subs=substitutions)
                print("yyy")
                print(expr)
                print(content)
                if float(content) == int(content):
                    content= int(content)

            answer_options.append({
                'id': opt.id,
                'content': content,
                'is_correct': opt.is_correct,
                'format': opt.display_format
            })
        random.shuffle(answer_options)
        return answer_options
    
    def randomize_variables(self, task):
        variables = Variable.objects.filter(task=task)
        for variable in variables:
            if variable.choices:
                choices = variable.choices
            else:
                choices = []
                for var in np.arange(variable.min_value, variable.max_value + variable.step, variable.step):
                    choices.append(str(round(var, 4)))

            random_choice = random.choice(choices)
            variable.original_value = random_choice

        return variables

class GetHintView(generic.View):
    def get(self, request, task_id):
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return render(request, 'matematyka/hint.html', {'error': 'Zadanie nie istnieje'})
        # issue_id=request.session.get('issue_id')
        try:
            issue = Issue.objects.get(id=request.session.get('issue_id'))
            user = request.user if request.user.is_authenticated else None
            if user:        
                user_answer, _ = UserAnswer.objects.get_or_create(user=request.user, issue=issue)
            else:
                user_answer, _ = UserAnswer.objects.get_or_create(user=None, issue=issue)
            user_answer.used_hint = True
            user_answer.save()

        except Issue.DoesNotExist:
            pass

        if not task.hint:
            return render(request, 'matematyka/hint.html', {'error': 'Brak wskazówki dla tego zadania'})

        return render(request, 'matematyka/hint.html', {'hint': task.hint})

class GetSolutionView(generic.View):
    def get(self, request, task_id):
       
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return render(request, 'matematyka/solution.html', {'error': 'Zadanie nie istnieje'})
        
        try:
            solution = Solution.objects.get(task=task)
        except Solution.DoesNotExist:
            return render(request, 'matematyka/solution.html', {'error': 'Brak rozwiązania dla tego zadania'})

        issue_id = request.session.get('submitted_issue_id')
        print(f"Issue ID: {issue_id}")
        variables = list(UsedVariable.objects.filter(issue__id=issue_id))
        print(f"Variables: {variables}")
        value_map = {var.variable_name: var.variable_value for var in variables}
        print(f"Value Map: {value_map}")
        rendered_solution = solution.content
        print(f"Raw Solution: {rendered_solution}")
        template_solution = Template(rendered_solution)
        print(f"Template Solution: {template_solution}")
        rendered_solution = template_solution.render(Context(value_map))
        print(f"Rendered Solution: {rendered_solution}")

        return render(request, 'matematyka/solution.html', {'solution': rendered_solution})

class SubmitAnswerView(generic.View):
    def post(self, request, task_id):

        selected_answer_id = request.POST.get('answer')
        request.session['submitted_issue_id'] = request.session.pop('issue_id', None)
        request.session['selected_answer_id'] = selected_answer_id

        return redirect('answer_result', task_id=task_id)
    

class AnswerResultView(generic.View):
    def get(self, request, task_id):
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return render(request, 'matematyka/issue.html', {'error': 'Zadanie nie istnieje'})
                
        try:
            issue = Issue.objects.get(id=request.session.get('submitted_issue_id'))
        except Issue.DoesNotExist:
            return render(request, 'matematyka/issue.html', {'error': 'Brak aktywnego zadania'})
        
        user = request.user if request.user.is_authenticated else None

        if user:
            user_answer, created = UserAnswer.objects.get_or_create(user=user, issue=issue)
        else:
            user_answer, created = UserAnswer.objects.get_or_create(user=None, issue=issue)
        if created:
            user_answer.used_hint = False

        selected_answer_id = request.session.get('selected_answer_id')
        if selected_answer_id:
            try:
                selected_option = AnswerOption.objects.get(id=selected_answer_id)
                user_answer.answer_date = timezone.now()
                user_answer.save()
                user_answer.answer_options.set([selected_option])
            except AnswerOption.DoesNotExist:
                # błąd: odpowiedź nie istnieje
                return render(request, 'matematyka/issue.html', {
                    'issue': issue,
                    'task': task,
                    'error': 'Wybrana odpowiedź nie istnieje!'
                })
        else:
            return render(request, 'matematyka/issue.html', {
                'issue': issue,
                'task': task,
                'error': 'Musisz zaznaczyć odpowiedź przed wysłaniem!'
            })            
        correct_answer = AnswerOption.objects.filter(task=task, is_correct=True).first()
        is_correct = selected_option == correct_answer

        variables = list(UsedVariable.objects.filter(issue=issue))
        value_map = {var.variable_name: var.variable_value for var in variables}

        user_answer = UserAnswer.objects.filter(issue=issue).first()

        symbols = {name: Symbol(name) for name in value_map}
        substitutions = {
            symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
            for k, v in value_map.items()
        }

        answer_options_db = AnswerOption.objects.filter(task=task)
        answers_instance = StartIssueView()
        answer_options = answers_instance.build_answer_options(answer_options_db, symbols, value_map, substitutions)

        raw_description = task.content
        template = Template(raw_description)
        rendered_description = template.render(Context(value_map))

        origin = request.session.get('origin')
        next_task_id = None

        if origin is not None:
            origin_type = origin.get('type')

            if origin_type == 'category':
                origin_id = origin.get('id')
                try:
                    category = Category.objects.get(id=origin_id)
                    next_task = category.tasks.filter(id__gt=task.id).order_by('id').first()
                    if next_task:
                        next_task_id = next_task.id
                except Category.DoesNotExist:
                    pass
            elif origin_type == 'exam':
                exam_level = origin.get('exam_level')
                exam_date = origin.get('exam_date')
                source = origin.get('source')
                next_task = Task.objects.filter(
                    task_level__exam_level=exam_level,
                    exam_date=exam_date,
                    source__name=source,
                    id__gt=task.id
                ).select_related("task_level").order_by('id').first()
                if next_task:
                    next_task_id = next_task.id
          

            # elif origin_type == 'random':
            #     ...

        return render(request, 'matematyka/answer.html', {
            'issue': issue,
            'task': task,
            'selected_option': selected_option,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'description': rendered_description,
            'answer_options': answer_options,
            'next_task_id': next_task_id,
        })

class RepeatIssueView(generic.View):
    def post(self, request):
        task_id = request.session.get('task_id')

        request.sesson.pop('submitted_issue_id')
        request.sesson.pop('selected_answer_id')

        return redirect('start_issue', task_id=task_id)
    
class NextIssueView(generic.View):
    def post(self, request):
        origin = request.session.get('origin')
        if not origin:
            return redirect('category_list')

        request.session.pop('submitted_issue_id')
        request.session.pop('selected_answer_id')

        # if origin['type'] == 'exam':
        #     exam_id = origin['id']
        #     # logika: pobierz kolejne zadanie z tego egzaminu
        #     return redirect('start_next_exam_task', exam_id=exam_id)
        # elif i ciąg dalszy

        if origin['type'] == 'category':
            category_id = origin['id']
            return redirect('start_next_category_task', category_id=category_id)

        # elif origin['type'] == 'random':
        #     return redirect('start_random_task')

        else:
            return redirect('category_list')
        
class ExamListView(generic.View):
    def get(self, request):

        exams = Task.objects.values(
            'exam_date', 'task_level__exam_level', 'source__name'
        ).annotate(task_count=Count('id')).order_by('exam_date')

        grouped_exams = {}
        for exam in exams:
            date = exam['exam_date']
            name = exam['task_level__exam_level']
            count = exam['task_count']
            source = exam['source__name']
            if date not in grouped_exams:
                grouped_exams[date] = []
            grouped_exams[date].append((name, count, source))

        context = {
            'grouped_exams': grouped_exams
        }
        return render(request, 'matematyka/exams.html', context)
    
class ExamTasksView(generic.ListView):
    model = Task
    template_name = 'matematyka/category_tasks.html'
    context_object_name = 'tasks'

    def get(self, request, *args, **kwargs):
        request.session['origin'] = {
            'type': 'exam',
            'exam_level': self.kwargs.get('exam_level'),
            'exam_date': self.kwargs.get('exam_date'),
            'source': self.kwargs.get('source'),
        }
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        exam_level = self.kwargs.get('exam_level')
        exam_date = self.kwargs.get('exam_date')
        source = self.kwargs.get('source')

        queryset = Task.objects.filter(
            task_level__exam_level=exam_level,
            exam_date=exam_date,
            source__name=source
        ).select_related('task_level')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tasks = context['tasks']

        issues = Issue.objects.filter(task__in=tasks)

        user = self.request.user if self.request.user.is_authenticated else None
        user_answers = UserAnswer.objects.filter(
            issue__in=issues,
            user=user
        ).select_related('issue', 'issue__task').prefetch_related('answer_options')

        total_attempts_original = defaultdict(int)
        correct_attempts_original = defaultdict(int)
        total_attempts_random = defaultdict(int)
        correct_attempts_random = defaultdict(int)

        for ua in user_answers:
            answer_option = ua.answer_options.first()
            if answer_option:
                if ua.issue.variable_is_random:
                    total_attempts_random[ua.issue.task_id] += 1
                    if answer_option.is_correct:
                        correct_attempts_random[ua.issue.task_id] += 1
                else:
                    total_attempts_original[ua.issue.task_id] += 1
                    if answer_option.is_correct:
                        correct_attempts_original[ua.issue.task_id] += 1

        tasks_with_attempts = []
        for task in tasks:
            tasks_with_attempts.append({
                'task': task,
                'total_attempts_original': total_attempts_original[task.id],
                'correct_attempts_original': correct_attempts_original[task.id],
                'total_attempts_random': total_attempts_random[task.id],
                'correct_attempts_random': correct_attempts_random[task.id],
            })

        context['tasks'] = tasks_with_attempts
        context['exam_level'] = self.kwargs.get('exam_level')
        context['exam_date'] = self.kwargs.get('exam_date')
        context['source'] = self.kwargs.get('source')
        return context
