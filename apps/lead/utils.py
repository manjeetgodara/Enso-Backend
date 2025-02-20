#self.request.user.groups.filter(name='Manager').exists()
def restrict_access_file_format(user, file_format):
    print("file_format: ", file_format)
    if user.groups.filter(name='CCE').exists() or user.groups.filter(name='SM').exists():
        return False
    elif file_format == 'pdf':
        return True  
    else:
        return False