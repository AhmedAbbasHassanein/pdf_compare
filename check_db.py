from app import app, db, User

# Create an application context
with app.app_context():
    # Query all users in the database
    users = User.query.all()

    # Print the users
    if users:
        print("Users in the database:")
        for user in users:
            print(f"ID: {user.id}, Username: {user.email}")
    else:
        print("No users found in the database.")