sudo pip install djangorestframework
sudo pip install markdown       # Markdown support for the browsable API.
sudo pip install django-filter  



workon d3_test
set DJANGO_SETTINGS_MODULE=d3_test.settings
python -m django runserver 8082
python setup.py install



install desktop/core (hue)

install pysignal


huePython  manage.py runserver --noreload --nothreading

[gjv1@alienware ext-py]$ for folder in $(ls); do sudo python $folder/setup.py install; done
