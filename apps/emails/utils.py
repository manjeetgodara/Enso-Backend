from auth.models import Users

def get_user_from_email(user_id):
    try:
        user = Users.objects.get(pk=user_id)
        from_email = user.email 
        return from_email
    except Users.DoesNotExist:
        return None