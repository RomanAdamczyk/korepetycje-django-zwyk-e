import pytest

from collections import defaultdict
from .. import models
# from ..views import build_solutions_map, build_answer_options
from sympy import sympify, Symbol
from django.template import Template, Context
from pprint import pprint


def build_answer_options(answer_options_db, solutions_map, value_map, substitutions):
    answer_options = []
    for opt in answer_options_db:
        # solution = value_map.get(opt.content)
        
        if opt.display_format == 'symbolic':
            raw_description = opt.content
            template = Template(raw_description)
            content = template.render(Context(value_map))

        elif opt.display_format == 'numeric':
            expr = sympify(opt.content,locals=solutions_map)
            content = expr.evalf(subs=substitutions)
            if float(content) == int(content):
                content= int(content)

        answer_options.append({
            'id': opt.id,
            'task_id': opt.task.id,
            'content': content,
            'is_correct': opt.is_correct,
            'format': opt.display_format
        })
  
    return answer_options

def build_solutions_map(additional_variables, value_map):
    for add_var in additional_variables:
        expr = sympify(add_var.formula)
        evaluated = expr.subs(value_map)

        try:
            numeric_result = round(float(N(evaluated)), 4)
        except TypeError as e:
            raise

        if numeric_result.is_integer():
            formatted = str(int(numeric_result))
        else:
            formatted = str(numeric_result)

        value_map[add_var.name] = formatted

    symbols = {name: Symbol(name) for name in value_map}
    
    substitutions = {
        symbols[k]: int(float(v)) if float(v).is_integer() else float(v)
        for k, v in value_map.items()
    }
    return symbols, substitutions


@pytest.mark.django_db
def test_no_duplicate_answers_for_task():
    answer_db = models.AnswerOption.objects.all()
    print(answer_db)
    variables = models.Variable.objects.all()
    additional_variables = models.AdditionalVariable.objects.all()

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

    solutions_map, substitutions = build_solutions_map(additional_variables, value_map)
    answer_options = build_answer_options(answer_db, solutions_map, value_map, substitutions)

    print("\nOdpowiedzi wygenerowane przez build_answer_options:")
    pprint(answer_options)  # albo print(answer_options)

    answers = defaultdict(list)
    for answer in answer_options:
        answers[answer.task_id].append(answer)