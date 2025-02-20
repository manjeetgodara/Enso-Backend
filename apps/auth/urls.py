from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login, name="login_user"),
    path("verifyotp/", views.verify_otp, name="verify_user_otp"),
    path('login-email/', views.login_email, name='login'),
    path('store/fcm-token', views.store_fcm_token, name='store_fcm_token'),
    path('change_password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('forgot_password/', views.ResetPasswordView.as_view(), name='request_forgot_password'),
    path('request-reset-email/',views.RequestPasswordResetEmail.as_view(),name='request-reset-email'),
    path('password-reset-complete/<uidb64>/<token>/',views.SetNewPasswordAPIView.as_view(),name='password-reset-complete'),
]