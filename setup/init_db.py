#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime
from uuid import uuid4

from urllib.parse import urlparse
from flask import json
from jsonschema import validate, ValidationError, SchemaError

from __init__ import app, db
from models import Degree, Graduation, Origin, Language, Course, User, ExportFormat
# Make sure that create_all works for all models (even ones that might be added in the future)
from models import *  # noqa


def validate_resources():
    resources = ('degrees', 'origins', 'courses', 'degrees', 'graduations', 'users', 'export_formats')

    for fname in resources:
        with app.open_resource('resource/{0}.json'.format(fname)) as fd_json, \
            app.open_resource('resource/{0}.schema'.format(fname)) as fd_schema:
            res_json = json.load(fd_json)
            res_schema = json.load(fd_schema)

            validate(res_json, res_schema)


def recreate_tables():
    db.drop_all()
    db.create_all()


def insert_resources():
    insert_degrees('resource/degrees.json')
    insert_graduations('resource/graduations.json')
    insert_origins('resource/origins.json')
    insert_courses('resource/courses.json')
    insert_export_formats('resource/export_formats.json')
    insert_users('resource/users.json')
    db.session.commit()


def insert_degrees(json_file):
    with app.open_resource(json_file) as fd:
        res = json.load(fd)

        for degree in res["degrees"]:
            db.session.add(Degree(degree))


def insert_graduations(json_file):
    with app.open_resource(json_file) as fd:
        res = json.load(fd)

        for graduation in res["graduations"]:
            db.session.add(Graduation(graduation))


def insert_origins(json_file):
    with app.open_resource(json_file) as fd:
        res = json.load(fd)

        print(" id | name | short_name | validate_registration | is_internal")
        for i, origin in enumerate(res["origins"]):
            #db.session.add(Origin(**origin))
            # type database object Origin -> one entry in the origin table
            db.session.add(Origin(name=origin["name"],
                                  short_name=origin["short_name"],
                                  validate_registration=origin["validate_registration"],
                                  is_internal=origin["is_internal"]))
            print(f"{i} | {origin['name']} | {origin['short_name']} | {origin['validate_registration']} | {origin['is_internal']}")






def insert_courses(json_file):
    with app.open_resource(json_file) as fd:
        res = json.load(fd)

        for language in res["languages"]:
            # pop 'courses' entry before creating the Language-object, so it doesn't get passed to the constructor
            courses = language.pop('courses', [])

            ref_lang = Language(
                # ISO 8601 / RFC 3339 -- better way to parse this?
                signup_begin=datetime.strptime(language.pop('signup_begin_iso_utc'), "%Y-%m-%dT%H:%M:%SZ"),
                signup_rnd_window_end=datetime.strptime(
                    language.pop('signup_random_window_end_iso_utc'), "%Y-%m-%dT%H:%M:%SZ"),
                signup_manual_end=datetime.strptime(language.pop('signup_manual_end'), "%Y-%m-%dT%H:%M:%SZ"),
                # see also Jsonschema RFC, date-time
                signup_end=datetime.strptime(language.pop('signup_end_iso_utc'), "%Y-%m-%dT%H:%M:%SZ"),
                signup_auto_end=datetime.strptime(language.pop('signup_auto_end_iso_utc'), "%Y-%m-%dT%H:%M:%SZ"),
                **language
            )

            for course in courses:
                for alt in course.pop('alternatives', [None]):
                    db.session.add(Course(
                        language=ref_lang,
                        alternative=alt,
                        **course
                    ))


def insert_export_formats(json_file):
    with app.open_resource(json_file) as fd:
        res = json.load(fd)

        for format in res["formats"]:
            if 'language' in format:
                lang_ref = Language.query.filter(Language.name == format.pop('language')).first()
            else:
                lang_ref = None

            #instance = format.pop('instance', ExportFormat.COURSE)

            db.session.add(ExportFormat(**format, language=lang_ref))


def insert_users(json_file):
    with app.open_resource(json_file) as fd:
        res = json.load(fd)

        print("create user accounts:")
        for user in res["users"]:
            roles = []
            for lang_name in user.pop('languages'):
                lang = Language.query.filter(Language.name == lang_name).first()
                if lang:
                    for course in lang.courses:
                        roles.append(Role(course=course, role=Role.COURSE_ADMIN))
                else:
                    print("  WARNING: language {} does not exist (user={})".format(lang_name, user["email"]))
            if user.pop('superuser'):
                roles.append(Role(role=Role.SUPERUSER))
            u = User(
                **user,
                roles=roles
            )
            pw = u.reset_password()
            print('  {} : {}'.format(u.email, pw))
            db.session.add(u)


def backup_postgresql_db(db_name: str):
    backup_file = 'backup_{0}.sql'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
    command = f"pg_dump {db_name} > {backup_file}"

    try:
        os.system(command)
        print(f"Backup created successfully: {backup_file}")
    except Exception as e:
        print(f"Error creating backup: {e}")

# Has to be done only once, to initialize the database;
# do not use this in regular code

if __name__ == '__main__':
    try:
        validate_resources()  # Strong exception safety guarantee
    except (ValidationError, SchemaError) as e:
        print(e)  # Stacktrace does not contain any useful information
        sys.exit()

    # Request polite confirmation
    token = uuid4().hex[:5]  # repeat random token of arbitrary length
    # OK, not an interactive process, try something else
    if 'YES_I_KNOW_THAT_WORLD_ENDS_NOW' in os.environ:
        user_in = token
    else:
        user_in = input('Create and drop tables using {0}\nConfirm by repeating the following token\n{1}\n'
                        .format(db, token))

    if token == user_in:
        recreate_tables()
        insert_resources()

        print('Import OK.')
    else:
        print('Aborting: {0} did not match token {1}'.format(user_in, token))

    # Assuming 'app' is your Flask application
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']

    # Parse the URI using urllib
    parsed_uri = urlparse(db_uri)

    # The database name is the 'path' part of the URI, without the leading '/'
    database_name = parsed_uri.path[1:]

    #backup_postgresql_db(database_name)
