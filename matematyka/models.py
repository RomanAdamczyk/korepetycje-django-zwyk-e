DISPLAY_FORMATS = [
    ('symbolic', 'Symboliczna'),     # np. sqrt(2), 5**12
    ('numeric', 'Liczbowa'),         # np. 1.41, 244140625
]

from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    '''
    Model representing a category of tasks.
    
    Attributes:
        name (str): The name of the category.'''

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class TaskGroup(models.Model):
    '''
    Model representing a group of tasks with the same initial content.
    
    Attributes:
        name (str): The name of the task group.'''
    
    shared_content = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.shared_content
    
class TaskLevel(models.Model):
    '''
    Model representing the level of a task.
    
    Attributes:
        exam_level (str): The level of the exam (e.g., "Matura podstawowa").
        school_level (str): The school level (e.g., "Szkoła podstawowa).
        class_number (int): The class number (e.g., 8 for "Klasa 8").'''
    
    exam_level = models.CharField(max_length=100, null=True, blank=True)
    school_level = models.CharField(max_length=100, null=True, blank=True)
    class_number = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = (('exam_level', 'school_level', 'class_number'),)
        # verbose_name = "Poziom zadania"
        # verbose_name_plural = "Poziomy zadań"

    def __str__(self):
        parts = filter(None, [self.exam_level, self.school_level, f"Klasa {self.class_number}" if self.class_number else None])
        return " - ".join(parts)


class TaskType(models.Model):
    '''
    Model representing the type of a task.
    
    Attributes:
        name (str): The name of the task type.'''
    
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Source(models.Model):
    '''
    Model representing the source of a task.
    
    Attributes:
        name (str): The name of the source (e.g., "CKE", "Operon").'''
    
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Task(models.Model):
    '''
    Model representing a task.
    
    Attributes:
        content (str): The content of the task.
        points (int): The number of points the task is worth.
        category (Category): The category of the task.
        task_group (TaskGroup): The group of tasks with the same initial content.
        task_level (TaskLevel): The level of the task.
        exam_date (datetime): The date of the exam.
        source (str): The source of the task (eg. CKE, Operon)
        hint (str): A hint for the task.
        sub_number (str): task number on the exam.
        task_type (TaskType): The type of the answers for the task.'''
    
    content = models.TextField()
    points = models.IntegerField(null=True, blank=True)
    category = models.ManyToManyField(Category, related_name='tasks')
    task_group = models.ForeignKey(TaskGroup, on_delete=models.SET_NULL,blank=True,null=True, related_name='tasks')
    task_level = models.ForeignKey(TaskLevel, on_delete=models.SET_NULL,blank=True,null=True, related_name='tasks')
    exam_date = models.DateField(null=True, blank=True)
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    hint = models.TextField(null=True, blank=True)
    sub_number = models.CharField(max_length=10, null=True, blank=True)
    task_type = models.ForeignKey(TaskType, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')

    def __str__(self):
        return f"id {self.id} - {self.content}"

class Issue(models.Model):
    '''
    Model that links the randomly selected data with the content of the task
    
    Attributes:
        task (Task): The task that this issue is related to.
        variable_is_random (bool): Indicates if the variables in this issue are randomly generated.
    '''
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='issues')
    variable_is_random = models.BooleanField(default=False)

    def __str__(self):
        return f"Issue {self.id} for Task {self.task.id}"

class UserProfile(models.Model):
    '''
    Model representing a user profile.
    
    Attributes:
        user (User): The user associated with this profile.
        username_for_admin (str): A username for the admin interface.'''
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    username_for_admin = models.CharField(max_length=100)

    def __str__(self):
        return f"User {self.user.id} - Nick {self.user.username} - Name: {self.username_for_admin}"
    
class AssignedTask(models.Model):
    '''
    Model representing a task assigned to a user.
    
    Attributes:
        user (User): The user to whom the task is assigned.
        task (Task): The task that is assigned.
        assigned_date (datetime): The date when the task was assigned.
        deadline (datetime): The deadline for the task.'''

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assigned_tasks')
    assigned_date = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Task {self.task_id} assigned to User {self.user_id}"
    
class Variable(models.Model):
    '''
    Model representing a variable used in tasks.
    
    Attributes:
        task (Task): The task to which the variable belongs.
        name (str): The name of the variable.
        original_value (float): The value of the variable.
        choices (dict): Possible choices for the variable, stored as a dictionary (JSONField).
        min_value (float): Minimum value for the variable.
        max_value (float): Maximum value for the variable.
        step (float): Step value for the variable.'''

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='variables', null=True, blank=True)
    name = models.CharField(max_length=100)
    original_value = models.CharField(max_length=100)
    choices = models.JSONField(null=True, blank=True)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    step = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('task', 'name')

    def __str__(self):
        return f"Variable {self.name} with value {self.original_value}"

class AdditionalVariable(models.Model):
    '''Model representing an additional computed variable for a task.
    
    Attributes:
        task (Task): The task to which the additional variable belongs.
        name (str): The name of the additional variable.
        formula (str): The formula used to compute the additional variable.
        save_result (bool): Indicates if the result of the formula should be saved to UsedVariable (solutions not).
        '''
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='additional_variables')
    name = models.CharField(max_length=100)  # np. 'potega', 'roznica'
    formula = models.CharField(max_length=200, null=True, blank=True)  # np. 'liczba1 ** liczba2'
    # save_result = models.BooleanField(default=False)  

    def __str__(self):
        return f"AdditionalVariable {self.name} for task {self.task.id}: {self.formula}"

class UsedVariable(models.Model):
    '''
    Model representing a variable used in a specific task or issue.
    
    Attributes:
        task (Task): The task in which the variable is used.
        issue (Issue): The issue in which the variable is used.
        variable (Variable): The variable that is used.
        variable_value (str): The value of the variable used in the task.
        '''
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='used_variables')
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='used_variables')
    variable = models.ForeignKey(Variable, on_delete=models.CASCADE, related_name='used_variables', null=True, blank=True)
    variable_name = models.CharField(max_length=100)
    variable_value = models.CharField(max_length=50)

    def __str__(self):
        variable_name = self.variable.name if self.variable else "(no variable)"
        return f"Variable {variable_name} for Task {self.task.id}"
    
class AnswerOption(models.Model):
    '''
    Model representing an answer option for a task.
    
    Attributes:
        task (Task): The task that this answer option is related to.
        content (str): The content of the answer option.
        is_correct (bool): Indicates if this answer option is correct.'''
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='answer_options')
    content = models.TextField()
    is_correct = models.BooleanField(default=False)
    display_format = models.CharField(max_length=20, choices=DISPLAY_FORMATS, default='numeric')

    def __str__(self):
        return f"Option for Task {self.task.id}: {self.content[:30]}..."

class UserAnswer(models.Model):
    '''
    Model representing an answer given by a user to a task.
    Attributes:
        user (User): The user who provided the answer.
        issue (Issue): The issue related to the task.
        answer_options (ManyToManyField): The answer options selected by the user.
        used_hint (bool): Indicates if a hint was used for this answer.
        answer_date (datetime): The date when the answer was given.'''
    
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='user_answers')
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='user_answers')
    answer_options = models.ManyToManyField(AnswerOption, related_name='user_answers', blank=True)
    used_hint = models.BooleanField(default=False)
    answer_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Odpowiedź #{self.id} od {self.user.username if self.user else 'Anonim'}"
    
class Solution(models.Model):
    '''
    Model representing a solution to a task.
    
    Attributes:
        task (Task): The task for which this solution is provided.
        content (str): The content of the solution.'''
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='solutions')
    content = models.TextField()

    def __str__(self):
        return f"Solution for Task {self.task.id}: {self.content[:30]}..."