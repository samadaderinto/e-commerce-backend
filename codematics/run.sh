source .env

if [ $ENV = "local" ]
then
  pipenv run python3 manage.py runserver 0.0.0.0:8000
elif [ $ENV = "dev" ]
then
  pipenv run gunicorn backend.asgi:application  --bind 0.0.0.0:8000 --workers=1 --threads=1 --worker-connections=10  -k uvicorn.workers.UvicornWorker
else
  pipenv run gunicorn backend.asgi:application --bind 0.0.0.0:8000 --workers=5 --threads=2 --worker-connections=1000  -k uvicorn.workers.UvicornWorker
fi
