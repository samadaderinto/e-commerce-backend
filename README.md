# E-commerce API

## Tech Stack

**Server:** Django, Django rest Framework, HTML

## Run Locally

Clone the project

```bash
  git clone [https://link-to-project](https://github.com/samadaderinto/e-commerce-backend)
```

Go to the project directory

```bash
  cd codematics
```

Install dependencies

```bash
  pip3 install -r requirements.txt
```
or 

```bash
  pip install -r requirements.txt
```

Create and Update migrations

```bash
  python3 manage.py makemigrations; python3 manage.py migrate
```

or 

```bash
  python manage.py makemigrations; python manage.py migrate
```

Start the server

```bash
  python3 manage.py runserver 
```

or 

```bash
  python manage.py runserver 
```


## Documentation

[Documentation](https://linktodocumentation)

## Project Structure

```
codematics
├── templates
│   └── email-templates
│      └── (html files)
│
└── media
│    └── images
│       └── (image files)
│
└── codematics
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── asgi.py
│    ├── settings.py
│    ├── urls.py 
│    ├── wsgi.py
│    └── __init__.py
│
└── affiliates
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│    
└──  cart
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└── core
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  payment
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py'
│
└──  product
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  staff
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  store
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  event_notification
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└── DockerFile
└── .dockerignore
└── deployment.md
└── entrypoint.sh
└── jenkinsfile
└── manage.py
└── pytest.ini
└── requirements.txt
```


1. migrations:
In Django, migrations are a way to manage changes to your models (database schema) over time. When you make changes to your models, such as adding a new field or changing an 
existing one, Django can automatically generate migration files that represent these changes.

2. settings.py:
In Django, this is a crucial file that holds various configuration settings for your django web application like database settings, middlewares, etc.

3. requirements.txt:
In Django, this file is often used to list all the Python packages that are required for the project to run. This file can be used with tools like pip to install all dependencies at once. 

4. urls.py
In Django, this files are used to define URL patterns for directing incoming web requests to the appropriate view functions
