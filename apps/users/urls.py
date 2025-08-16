from django.urls import path
from .views import *

app_name = 'apps.users'

urlpatterns = [
    path('list/', UserList.as_view(), name='user_list'),
    path('create/', UserCreate.as_view(), name='user_create'),
    path('update/<int:id>/', UserUpdate.as_view(), name='user_update'),
    path('delete/<int:id>/', UserDelete.as_view(), name='user_delete'),
    path('get_user/', GetUser.as_view(), name='get_user'),
    path('login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
]
