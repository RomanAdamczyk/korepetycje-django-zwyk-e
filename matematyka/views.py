from django.shortcuts import render, redirect
from django.views import generic
from django.template import Template, Context
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.contrib import messages
from django.utils import timezone
from sympy import sympify, N, Symbol
from collections import defaultdict
from django.db.models import Count, OuterRef, Prefetch, When, Case, Value
from django.conf import settings

from .models import Category, Issue, Task, UsedVariable, AnswerOption, AdditionalVariable, Variable, UserAnswer, Solution, AssignedTask
from .forms import RegisterForm
from .utils import format_value_map

import numpy as np
import random

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
        if form.cleaned_data.get('code') != settings.INVITE_CODE:
            form.add_error('code', 'Nieprawidłowy kod zaproszeniowy.')
            return self.form_invalid(form)
        
        user = form.save()
        messages.success(self.request, 'Rejestracja udana! Czekaj na aktywację konta przez administratora')
        user.is_active = False
        user.save(update_fields=['is_active'])
        default_group, created = Group.objects.get_or_create(name='Uzytkownicy')
        user.groups.add(default_group)

        return redirect('category_list')
class CategoryListView(generic.ListView):
    """
    Display a list of math problem categories.

    This view retrieves all categories from the database and attaches an
    additional attribute `task_count` to each category. The value of
    `task_count` represents the number of tasks assigned to the category.

    Attributes:
        model (Category): The model representing math categories.
        template_name (str): The template used to render the category list.
        context_object_name (str): The name of the context variable passed to the template.

    Methods:
        get_context_data(**kwargs):
            Extend the default context by adding the number of tasks for each category.
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
    """
    Display all tasks belonging to a specific category.

    This view retrieves a category based on its primary key (pk) and lists
    all associated tasks. It stores the origin of the request in the session
    to allow easy navigation back to the category list. Users can view each
    task with either original variables or randomized variables. 

    For authenticated users, the view also includes their attempts and
    results, showing statistics of correct and incorrect answers for
    both original and randomized versions of tasks.

    Attributes:
        model (Category): The model representing math categories.
        template_name (str): The template used to render the category tasks.
        context_object_name (str): The name of the context variable passed to the template.

    Methods:
        get(request, *args, **kwargs):
            Handles GET requests, retrieves the category object,
            and stores the request origin in the session.
        get_context_data(**kwargs):
            Extends the default context with tasks and user attempt statistics
            (total and correct attempts for both original and randomized tasks).
    """
 
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
        category_tasks = self.object.tasks.prefetch_related('category').all()
        
        issues = Issue.objects.filter(task__category=self.object)
        
        user = self.request.user if self.request.user.is_authenticated else None
        user_answers = UserAnswer.objects.filter(
            issue__in=issues,
            user=user
        ).select_related('issue', 'issue__task').prefetch_related('answer_options').distinct()

        assigned_tasks = AssignedTask.objects.filter(
            user=user, task__in=category_tasks
            ).prefetch_related(Prefetch(
                'task__issues__user_answers',
                 queryset=UserAnswer.objects.filter(
                     user = user,
                     ).select_related('issue__task', 'user').prefetch_related('answer_options')))
        
        assigned_by_task = {at.task_id: at for at in assigned_tasks}

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
                'category': self.object,
                'total_attempts_original': total_attempts_original[task.id],
                'correct_attempts_original': correct_attempts_original[task.id],
                'total_attempts_random': total_attempts_random[task.id],
                'correct_attempts_random': correct_attempts_random[task.id],
            })
            assigned = assigned_by_task.get(task.id)
            if assigned:
                tasks[-1]['is_assigned'] = True
                is_completed = assigned.completion_date
                tasks[-1]['is_completed'] = is_completed
                tasks[-1]['deadline'] = assigned.deadline if not is_completed else None
                overdue = assigned.deadline < timezone.now() if assigned.deadline else False
                tasks[-1]['overdue'] = overdue
            else:
                tasks[-1]['is_assigned'] = False
                tasks[-1]['is_completed'] = False
                tasks[-1]['deadline'] = None
                tasks[-1]['overdue'] = False
                        
        context['tasks'] = tasks
        context['view_type'] = 'category'
        return context
    
class StartIssueView(generic.View):
    """
    Start a new issue for a given task.
    
    This view handles the creation of a new issue for a task, either with
    random or original variables. It retrieves the task based on the provided
    task_id and checks if an issue already exists in the session. If it does,
    it uses the existing issue; otherwise, it creates a new one. The view also
    retrieves the variables associated with the task, either randomizing them
    or using their original values. It builds the answer options based on the
    task's answer options and the variables used in the issue. The task's
    description is rendered with the variables, and the context is prepared
    for rendering the issue template.
    The view also handles the case where the user has previously submitted an
    issue and retrieves the variables used in that issue to display the
    four answer options.

    Methods:

        get(request, task_id):
        Handles GET requests to start an issue for a specific task.
        It checks for an existing issue in the session, creates a new issue if
        none exists, and retrieves the task's variables and answer options.
        It renders the task's description with the variables and prepares the
        context for rendering the issue template.
        
        build_solutions_map(issue, additional_variables, value_map):
        Builds a map of solutions for the issue based on additional variables
        and the value map of variables used in the issue. It evaluates the
        additional variables' formulas using the value map and stores the
        results in the UsedVariable model. It returns a dictionary of symbols
        and substitutions for rendering the answer options.

        build_answer_options(answer_options_db, solutions_map, value_map, substitutions):
        Builds a list of answer options for the issue based on the task's
        answer options. It evaluates the content of each answer option using
        the solutions map and value map. The answer options are formatted
        according to their display format (symbolic or numeric) and shuffled
        before being returned. The method also handles the case where the
        content is symbolic or numeric, rendering it with the appropriate
        context. It returns a list of dictionaries containing the answer
        option's ID, content, correctness, and format.
        
        randomize_variables(task):
        Randomizes the variables for a given task. It retrieves the variables
        associated with the task and randomly selects a value for each variable
        from its choices or generates a range of values. The method updates
        the original value of each variable with the randomly selected value.
        It returns the list of variables with their new randomized values.        
    """
    def get(self, request, task_id):
        issue = None
        task = Task.objects.select_related('task_level', 'source', 'task_type').prefetch_related(
                    'category').get(id=task_id)
        exam_info = {
            'number': task.sub_number,
            'level': task.task_level.exam_level if task.task_level else 'Nieznany',
            'date': task.exam_date,
            'source': task.source.name if task.source else 'Nieznane',
            'categories': [cat.name for cat in task.category.all()]}        

        if 'issue_id' in request.session:
            try:
                existing_issue = Issue.objects.get(id=request.session['issue_id'])
                if existing_issue.task.id == task_id:
                    issue = existing_issue
                    used_variables = list(UsedVariable.objects.filter(issue=issue))
                    value_map = {used.variable_name: used.variable_value for used in used_variables}

                    for used in used_variables:
                        split = used.split_map
                        if split:
                            value_map[f"{used.variable_name}_sign"] = split['sign']
                            value_map[f"{used.variable_name}_abs"] = split['abs']
            
                    value_map = format_value_map(value_map)
     
                    numerical_value_map = {k: v for k, v in value_map.items() if not k.endswith('_sign') and not k.endswith('_abs')}
                    symbols = {name: Symbol(name) for name in numerical_value_map}
                    substitutions = {
                        symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
                        for k, v in numerical_value_map.items()
                    }
                    answer_options_db = AnswerOption.objects.filter(task=task)
                    answer_options = self.build_answer_options(answer_options_db, symbols, value_map, substitutions)
            except Issue.DoesNotExist:
                pass

        if issue is None:
            random_param = self.request.GET.get("random") == "true"
            issue = Issue.objects.create(task=task, variable_is_random=random_param)
            request.session['issue_id'] = issue.id

            if random_param:
                variables = self.randomize_variables(task=task)
            else:
                variables = Variable.objects.filter(task=task)

            additional_variables = AdditionalVariable.objects.filter(task=task)
            answer_options_db = AnswerOption.objects.filter(task=task)

            value_map = {}
            used_variables = []
            print("\n[DEBUG] Zmienna random_param:", random_param)
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

                used_variable = UsedVariable.objects.create(
                    task=task,
                    issue=issue,
                    variable=variable,
                    additional_variable=None,
                    variable_name=variable.name,
                    variable_value=str(value)
                )
                used_variables.append(used_variable)

            print("\n[DEBUG] value_map PO zwykłych zmiennych:", value_map)

            for used in used_variables:
                split = used.split_map
                if split:
                    value_map[f"{used.variable_name}_sign"] = split['sign']
                    value_map[f"{used.variable_name}_abs"] = split['abs']
                    
            value_map = format_value_map(value_map)
            print("Value map after formatting:", value_map)
            solutions_map, substitutions = self.build_solutions_map(issue, additional_variables, value_map)
            print("Solutions map:", solutions_map)
            numerical_value_map = {k: v for k, v in value_map.items() if not k.endswith('_sign') and not k.endswith('_abs')}
            symbols = {name: Symbol(name) for name in numerical_value_map}
            substitutions = {
                symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
                for k, v in numerical_value_map.items()
            }    
            answer_options = self.build_answer_options(answer_options_db, solutions_map, value_map, substitutions)

        raw_description = task.content
        template = Template(raw_description)
        rendered_description = template.render(Context(value_map))
        context = {
            'issue': issue,
            'variables': value_map,
            'answer_options': answer_options,
            'description': rendered_description,
            'exam_info': exam_info,
            }
       
        return render(request, 'matematyka/issue.html', context=context)

    def build_solutions_map(self,issue,additional_variables, value_map):
        used_variables = []
        for add_var in additional_variables:
            print(f"\n[DEBUG] Evaluating additional variable: {add_var.name} with formula: {add_var.formula} and value map: {value_map}")
            expr = sympify(add_var.formula)
            print(f"[DEBUG] Parsed expression for {add_var.name}: {expr}")
            numerical_value_map = {
                k: v for k, v in value_map.items() 
                if not k.endswith('_sign') and not k.endswith('_abs')
            }
            if hasattr(add_var, 'split_map'):
                split = add_var.split_map
                if split:
                    value_map[f"{add_var.variable_name}_sign"] = split['sign']
                    value_map[f"{add_var.variable_name}_abs"] = split['abs']
            print(f"[DEBUG] Value map before evaluating {add_var.name}: {value_map}")                
            evaluated = expr.subs(numerical_value_map)
            print(f"[DEBUG] Evaluated expression for {add_var.name}: {evaluated}")
            try:
                numeric_result = round(float(N(evaluated)), 4)
            except TypeError as e:
                raise
            print(f"[DEBUG] Numeric result for {add_var.name}: {numeric_result}")
            if numeric_result.is_integer():
                formatted = str(int(numeric_result))
            else:
                formatted = str(numeric_result)
            print(f"[DEBUG] Formatted result for {add_var.name}: {formatted}")
            value_map[add_var.name] = formatted
            print(f"[DEBUG] Updated value map with {add_var.name}: {value_map}")    
            used_variable = UsedVariable.objects.create(
                task=issue.task,
                issue=issue,
                variable=None,
                additional_variable=add_var,
                variable_name=add_var.name,
                variable_value=str(numeric_result)
            )
            used_variable.split_sign = add_var.split_sign
            used_variable.save(update_fields=['split_values'])
            used_variables.append(used_variable)
            print(f"[DEBUG] Evaluated {add_var.name}: {formatted} (raw: {evaluated})")

        for used in used_variables:
            split = used.split_map
            if split:
                value_map[f"{used.variable_name}_sign"] = split['sign']
                value_map[f"{used.variable_name}_abs"] = split['abs']
                
        value_map = format_value_map(value_map)
        numerical_value_map = {k: v for k, v in value_map.items() if not k.endswith('_sign') and not k.endswith('_abs')}
        symbols = {name: Symbol(name) for name in numerical_value_map}
        
        substitutions = {
            symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
            for k, v in numerical_value_map.items()
        }
        return symbols, substitutions


    def build_answer_options(self, answer_options_db, solutions_map, value_map, substitutions):
        answer_options = []
        print("Building answer options with value map:", value_map)
        for opt in answer_options_db:
            print(f"Building option: {opt.content} with format {opt.display_format}")
            solution = value_map.get(opt.content)
            
            raw_description = opt.content
            template = Template(raw_description)
            rendered_description = template.render(Context(value_map))
           
            answer_options.append({
                'id': opt.id,
                'content': rendered_description,
                'is_correct': opt.is_correct,
                'format': opt.display_format
            })
            print(f"Option: {opt.content}, Evaluated: {rendered_description}, Is Correct: {opt.is_correct}")
        random.shuffle(answer_options)
        return answer_options
    
    def randomize_variables(self, task):
        variables = Variable.objects.filter(task=task)
        choices_dict= {}
        for variable in variables:
            if variable.choices:
                choices = variable.choices
            else:
                without_values = getattr(variable, 'without_value', [])
                choices = []
                for var in np.arange(variable.min_value, variable.max_value + variable.step, variable.step):
                    if var not in without_values:
                        choices.append(str(round(var, 4)))
            
            choices_dict[variable.id] = choices

        groups = defaultdict(list)
        for variable in variables:
            group = getattr(variable, 'unique_group', None)
            if group:
                groups[group].append(variable)
            else:
                random_choice = random.choice(choices_dict[variable.id])  #without group
                variable.original_value = random_choice

        for group_name, group_vars in groups.items():
            max_attempts = 1000  # protection against infinite loop
            attempts = 0
            while attempts < max_attempts:
                values = {}
                unique = True
                for variable in group_vars:
                   choice = random.choice(choices_dict[variable.id])
                   values[variable.id] = choice

                if len(set(values.values())) == len(values):
                    for variable in group_vars:
                        variable.original_value = values[variable.id]
                    break
                attempts += 1
            else:
                raise Exception(f"Nie można wygenerować unikalnych wartości dla grupy zmiennych: {group_name}")
        return variables
    
class GetHintView(generic.View):
    def get(self, request, task_id):
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return render(request, 'matematyka/hint.html', {'error': 'Zadanie nie istnieje'})

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
        used_variables = list(UsedVariable.objects.filter(issue__id=issue_id))
        value_map = {var.variable_name: var.variable_value for var in used_variables}

        for used in used_variables:
            split = used.split_map
            if split:
                value_map[f"{used.variable_name}_sign"] = split['sign']
                value_map[f"{used.variable_name}_abs"] = split['abs']    
        
        value_map = format_value_map(value_map)

        rendered_solution = solution.content
        template_solution = Template(rendered_solution)
        rendered_solution = template_solution.render(Context(value_map))

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
            issue = Issue.objects.select_related('task__task_level','task__source', 'task__task_type').prefetch_related(
                'task__category').get(id=request.session.get('submitted_issue_id'))
        except Issue.DoesNotExist:
            return render(request, 'matematyka/issue.html', {'error': 'Brak aktywnego zadania'})
        
        task = issue.task
        exam_info = {
            'number': task.sub_number,
            'level': task.task_level.exam_level if task.task_level else 'Nieznany',
            'date': task.exam_date,
            'source': task.source.name if task.source else 'Nieznane',
            'categories': [cat.name for cat in task.category.all()]}        

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

        used_variables = list(UsedVariable.objects.filter(issue=issue))
        value_map = {var.variable_name: var.variable_value for var in used_variables}

        for used in used_variables:
            split = used.split_map

            if split:
                value_map[f"{used.variable_name}_sign"] = split['sign']
                value_map[f"{used.variable_name}_abs"] = split['abs']    

        value_map = format_value_map(value_map)
        numeric_value_map = {k: v for k, v in value_map.items() if not k.endswith('_sign') and not k.endswith('_abs')}

        user_answer = UserAnswer.objects.filter(issue=issue).first()

        symbols = {name: Symbol(name) for name in numeric_value_map}
        substitutions = {
            symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
            for k, v in numeric_value_map.items()
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
          
        assigned_task = AssignedTask.objects.filter(user=user, task=task, is_completed=False).first()
        if is_correct and assigned_task:
            assigned_task.is_completed = True
            assigned_task.save()

        return render(request, 'matematyka/answer.html', {
            'issue': issue,
            'task': task,
            'selected_option': selected_option,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'description': rendered_description,
            'answer_options': answer_options,
            'next_task_id': next_task_id,
            'exam_info': exam_info,
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

        if origin['type'] == 'category':
            category_id = origin['id']
            return redirect('start_next_category_task', category_id=category_id)
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
        ).prefetch_related('category').select_related('task_level')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam_tasks = context['tasks']

        issues = Issue.objects.filter(task__in=exam_tasks)

        user = self.request.user if self.request.user.is_authenticated else None
        user_answers = UserAnswer.objects.filter(
            issue__in=issues,
            user=user
        ).select_related('issue', 'issue__task').prefetch_related('answer_options')

        assigned_tasks = AssignedTask.objects.filter(
            user=user, task__in=exam_tasks
            ).prefetch_related(Prefetch(
                'task__issues__user_answers',
                 queryset=UserAnswer.objects.filter(
                     user = user,
                     ).select_related('issue__task', 'user').prefetch_related('answer_options')))
        
        assigned_by_task = {at.task_id: at for at in assigned_tasks}

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
        for task in exam_tasks:
            tasks.append({
                'task': task,
                'total_attempts_original': total_attempts_original[task.id],
                'correct_attempts_original': correct_attempts_original[task.id],
                'total_attempts_random': total_attempts_random[task.id],
                'correct_attempts_random': correct_attempts_random[task.id],
                'category': task.category.all()
            })
            assigned = assigned_by_task.get(task.id)
            if assigned:
                tasks[-1]['is_assigned'] = True
                is_completed = assigned.completion_date
                tasks[-1]['is_completed'] = is_completed
                tasks[-1]['deadline'] = assigned.deadline if not is_completed else None
                overdue = assigned.deadline < timezone.now() if assigned.deadline else False
                tasks[-1]['overdue'] = overdue
            else:
                tasks[-1]['is_assigned'] = False
                tasks[-1]['is_completed'] = False
                tasks[-1]['deadline'] = None
                tasks[-1]['overdue'] = False
    
        context['tasks'] = tasks
        context['exam_level'] = self.kwargs.get('exam_level')
        context['exam_date'] = self.kwargs.get('exam_date')
        context['source'] = self.kwargs.get('source')
        context['view_type'] = 'exam'
        return context

class AssignedTasksView(generic.ListView):
    model = AssignedTask
    template_name = 'matematyka/category_tasks.html'
    context_object_name = 'assigned_tasks'

    def get(self, request, *args, **kwargs):
        request.session['origin'] = {
            'type': 'assigned',
        }
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        queryset = AssignedTask.objects.filter(user=user).select_related('task').annotate(
            is_completed_flag=(Case(When(is_completed= True,then=Value(1)),default=Value(0)))).order_by(
                'is_completed_flag','deadline').prefetch_related('task__category')
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_completed'] = self.request.GET.get('hide_completed')
        hide_completed = self.request.GET.get('hide_completed')
        user = self.request.user if self.request.user.is_authenticated else None
        tasks_list = [at.task for at in self.object_list]
        issues = Issue.objects.filter(task__in=tasks_list)
        user_answers = UserAnswer.objects.filter(
            issue__in=issues,
            user=user
        ).select_related('issue', 'issue__task').prefetch_related('answer_options').distinct()

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
        for assigned in self.object_list:
            is_completed = assigned.completion_date
            if not hide_completed or not is_completed or (is_completed and assigned.deadline >= timezone.now()):
                task = assigned.task
                overdue = assigned.deadline < timezone.now() if assigned.deadline else False

                tasks.append({
                    'task': task,
                    'category': task.category.all(),
                    'total_attempts_original': total_attempts_original[task.id],
                    'correct_attempts_original': correct_attempts_original[task.id],
                    'total_attempts_random': total_attempts_random[task.id],
                    'correct_attempts_random': correct_attempts_random[task.id],
                    'is_assigned' : True,
                    'is_completed' : assigned.completion_date,
                    'deadline' : assigned.deadline if not assigned.completion_date else None,
                    'overdue' : overdue,
                })
 
        context['tasks'] = tasks
        context['view_type'] = 'assigned'

        return context