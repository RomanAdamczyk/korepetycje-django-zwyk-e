from django.contrib import admin
from matematyka.models import Category, TaskGroup, TaskLevel, Task, Issue, UserProfile, AssignedTask, Variable, UsedVariable, AnswerOption, UserAnswer, TaskType, AdditionalVariable, Source, Solution

class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']

class TaskGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'shared_content']
    search_fields = ['shared_content']

class TaskLevelAdmin(admin.ModelAdmin):
    list_display = ['id', 'exam_level', 'school_level', 'class_number']
    search_fields = ['exam_level', 'school_level']

class SourceAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']

class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'content', 'points', 'exam_date', 'source', 'hint', 'sub_number']
    search_fields = ['content', 'source']
    list_filter = ['exam_date', 'category', 'task_group', 'task_level']
    filter_horizontal = ['category']

class IssueAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'task_id',
        'exam_level',
        'sub_number',
        'exam_date',
        'variable_is_random',
    ]

    def task_id(self, obj):
        return obj.task.id
    task_id.short_description = "Task ID"

    def exam_level(self, obj):
        return obj.task.task_level.exam_level if obj.task.task_level else "-"
    exam_level.short_description = "exam_level"

    def sub_number(self, obj):
        return obj.task.sub_number or "-"
    sub_number.short_description = "sub_number"

    def exam_date(self, obj):
        return obj.task.exam_date or "-"
    exam_date.short_description = "exam_date"

    search_fields = ['task__content']
    list_filter = ['task']

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'username_for_admin']
    search_fields = ['user__username', 'username_for_admin']

class AssignedTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'task', 'assigned_date', 'deadline']
    search_fields = ['user__username', 'task__content']
    list_filter = ['assigned_date', 'deadline']

class VariableAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_id', 'name', 'min_value', 'max_value','step','choices', 'original_value']

    def task_id(self, obj):
        return obj.task.id
    task_id.short_description = "Task ID"

    search_fields = ['name']
    list_filter = ['task_id']

class AdditionalVariableAdmin(admin.ModelAdmin):
    list_display = ['id', 'task__id', 'name', 'formula']

class UsedVariableAdmin(admin.ModelAdmin):
    list_display = ['id', 'variable', 'issue', 'variable_name', 'variable_value']
    search_fields = ['variable__variable_name', 'issue__task__content']
    list_filter = ['issue']

class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'task__id','content', 'is_correct', 'display_format']
    search_fields = ['task__content', 'content']
    list_filter = ['is_correct']

class TaskTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']

class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'get_task', 'get_answer_option_list', 'used_hint']

    def get_task(self, obj):
        first_option = obj.answer_options.first()
        return first_option.task if first_option else '—'
    get_task.short_description = 'Task'

    def get_answer_option_list(self, obj):
        return ", ".join([opt.content for opt in obj.answer_options.all()])
    get_answer_option_list.short_description = 'Answer Options'

    search_fields = ['user__username', 'answer_options__task__content', 'answer_options__content']
    list_filter = ['used_hint']
    
class SolutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'content']
    search_fields = ['task']
    list_filter = ['task']


admin.site.register(Category, CategoryAdmin)
admin.site.register(TaskGroup, TaskGroupAdmin) 
admin.site.register(TaskLevel, TaskLevelAdmin)
admin.site.register(Source, SourceAdmin)
admin.site.register(Task, TaskAdmin)
admin.site.register(Issue, IssueAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(AssignedTask, AssignedTaskAdmin)
admin.site.register(Variable, VariableAdmin)
admin.site.register(AdditionalVariable, AdditionalVariableAdmin)
admin.site.register(UsedVariable, UsedVariableAdmin)
admin.site.register(AnswerOption, AnswerOptionAdmin)
admin.site.register(UserAnswer, UserAnswerAdmin)
admin.site.register(TaskType, TaskTypeAdmin)
admin.site.register(Solution, SolutionAdmin)