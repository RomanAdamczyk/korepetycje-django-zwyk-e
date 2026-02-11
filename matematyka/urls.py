from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView

from . import views

urlpatterns = [
    path('login/', LoginView.as_view(template_name='matematyka/login.html'), name='login'),
    path('logout/', LogoutView.as_view(template_name="matematyka/logout.html"), name='logout'),
    path("register/", views.RegisterView.as_view(), name="register"),
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('category/<int:pk>/tasks/', views.CategoryTasksView.as_view(), name='category_tasks'),
    path('exams/', views.ExamListView.as_view(), name='exam_list'),
    path('exams/<str:exam_level>/<str:exam_date>/<str:source>/', views.ExamTasksView.as_view(), name='exam_tasks'),
    path('tasks/<int:task_id>/', views.StartIssueView.as_view(), name='start_issue'),
    path('tasks/<int:task_id>/hint/', views.GetHintView.as_view(), name='get_hint'),
    path('tasks/<int:task_id>/answer/submit/', views.SubmitAnswerView.as_view(), name='answer'),
    path('tasks/<int:task_id>/answer/result/', views.AnswerResultView.as_view(), name='answer_result'),
    path('tasks/<int:task_id>/answer/result/solution', views.GetSolutionView.as_view(), name='get_solution'),
    path('tasks/assigned/', views.AssignedTasksView.as_view(), name='assigned_tasks'),
]
