#!/usr/bin/env python

import argparse
import base64
import datetime
import logging
import mimetypes
import os
import re
import subprocess
import sys
import time
import uuid
import yaml
from PIL import Image

from ss.gd import GoogleDrive


parser = argparse.ArgumentParser(prog=sys.argv[0])
parser.add_argument('target', default=None, nargs='*')
parser.add_argument('--debug', action='store_true', default=False)

logging.basicConfig()
log = logging.getLogger(__name__)

# Globals
RE_STRIP_URL = re.compile('^(http|https)://')
GD = None
GD_PARENTS = dict()
GD_THIS_TIMES = dict()
IMG_MAX_WIDTH = 4000
IMG_MAX_HEIGHT = 8000


def renderURL(url, output, size=None, headers=None):
    if size is None:
        size = (2000, 2000)

    cmd = [
        '/usr/local/bin/phantomjs',
        '/opt/renderURL.js',
        url,
        output,
        '--viewport',
        '%sx%s' % size[:2],
    ]

    if headers is not None:
        for k, v in headers.items():
            cmd.append('--header')
            cmd.append('%s: %s' % (k, v))

    exit = subprocess.call(cmd, stdout=subprocess.PIPE)

    return exit == 0


def handle_config_service(name, s, config):
    # # schedule
    # schedule = s['schedule']
    # if schedule.index(':'):
    #     t = datetime.time(*map(int, schedule.split(':')))
    #     t = (datetime.datetime.combine(datetime.date.today(), t) + datetime.timedelta(hours=9)).time()
    #     s['schedule'] = t

    devices = list()
    for i in set(s['devices']):
        device = config.get('preset').get(i)
        devices.append(
            dict(
                name=i,
                flip=device.get('flip', True),
                size=(device['width'], device['height']),
            )
        )

    s['devices'] = devices
    s['name'] = name

    return s


def read_config(f):
    config = yaml.load(file(f).read())

    services = map(
        lambda x: handle_config_service(x[0], x[1], config),
        map(
            lambda x: (x, config.get(x),),
            filter(lambda x: x not in ('preset', 'config'), config.keys()),
        )
    )

    return dict(
        config=config['config'],
        preset=config['preset'],
        services=services,
    )


def handle_image(f):
    im = Image.open(f)
    w, h = im.size
    if w < IMG_MAX_WIDTH and h < IMG_MAX_HEIGHT:
        return (f, False)

    if w > IMG_MAX_WIDTH:
        w = IMG_MAX_WIDTH
    if h > IMG_MAX_HEIGHT:
        h = IMG_MAX_HEIGHT

    cropped = os.path.join(
        os.path.dirname(f),
        ('croppred-%s' % os.path.basename(f))
    )
    im.crop((0, 0, w, h)).save(cropped)

    return (cropped, True)


def upload(f, service, device, size, ext='jpg', **kw):
    service_name = service.get('name')
    filename = '%(device)s%(flipped)s%(cropped)s.%(ext)s' % dict(
        service=service_name,
        device=device.get('name'),
        size=('%dx%d' % size[:2]),
        time=datetime.datetime.now().strftime('%Y%m%d.%H%M%S'),
        ext=ext,
        flipped=('-%s' % size[2]) if size[2] else '',
        cropped='-cropped' if kw.get('cropped') else '',
    )
    log.debug('\ttrying to upload: `%s`', filename)

    # check `this_time`
    now = datetime.datetime.now() + datetime.timedelta(hours=9)
    if GD_THIS_TIMES.get(service_name) is None:  # create new this time folder
        log.debug('\tcreate new this time folder: `%s`', now.isoformat())

        this_time = GD.mkdir(
            now.isoformat(),
            parent_ids=(GD_PARENTS.get(service_name),),
        )
        GD_THIS_TIMES[service_name] = this_time.get('id')

    success = GD.upload(
        f,
        filename=filename,
        mimetype=mimetypes.guess_type(filename)[0],
        parent_ids=(GD_THIS_TIMES[service_name],),
        description='''* size: %(size)s
* service: %(service)s
* device: %(device)s
* shooting time: %(now)s KST
* flipped: %(flipped)s
        ''' % dict(
            service=service_name,
            device=device.get('name'),
            size=('%dx%d' % size[:2]),
            now=now.isoformat(),
            flipped='yes' if size[2] else 'no',
        ),
    )

    return success.get('name') == filename


if __name__ == '__main__':
    options = parser.parse_args()

    log.setLevel(logging.DEBUG if options.debug else logging.ERROR)

    log.debug('options: %s', options)

    config_file = os.path.join(
        os.path.dirname(os.path.abspath(sys.argv[0])),
        'config.yml',
    )
    log.debug('load config from `%s`', config_file)
    config = read_config(config_file)

    ################################################################################
    # google drive
    log.debug('> trying to connect to google drive')
    drive_config = config['config']['google-drive']
    GD = GoogleDrive(
        base64.b64decode(drive_config['credential']),
        drive_config['account-email'],
        drive_config['user-email'],
    )

    # create folder for service
    service_names = filter(
        lambda x: not options.target or x in options.target,
        map(lambda x: x.get('name'), config['services']),
    )

    query = 'mimeType="application/vnd.google-apps.folder" and trashed != true and "%s" in parents' % drive_config['parent-id']
    log.debug('\tget files with query: `%s`', query)
    for i in GD.get_files(query=query, spaces='drive'):
        if i.get('name') in service_names:
            log.debug('\tfound existing service folder, `%s`', i.get('name'))
            GD_PARENTS[i.get('name')] = i.get('id')

    for i in service_names:
        if i in GD_PARENTS:
            continue

        service_folder = GD.mkdir(
            i,
            parent_ids=(drive_config['parent-id'],),
        )
        if type(i) in (str,):
            i = i.decode('utf-8')

        GD_PARENTS[i] = service_folder.get('id')
        log.debug('\tcreate new service folder, `%s`', i)

    ################################################################################

    headers = config['config'].get('headers')

    log.debug('starting to shooting')
    max_retries = 10
    for service in config['services']:
        if options.target and service.get('name') not in options.target:
            continue

        log.debug('> service: `%s`', service.get('name'))
        for device in service.get('devices'):
            log.debug('\tdevice: `%s`', device.get('name'))

            size = list(device.get('size'))
            size.append('')

            sizes = [tuple(size)]
            if device.get('flip'):
                sizes.append((device.get('size')[1], device.get('size')[0], 'flipped'))

            for size in sizes:
                log.debug('\tsize: `%s`', size)

                s = time.time()
                output = os.path.join(
                    config['config'].get('output-directory'),
                    ('%s.%s' % (uuid.uuid1().hex, config.get('extension', 'jpg'))),
                )
                directory = os.path.dirname(output)
                if not os.path.exists(directory):
                    os.makedirs(directory)

                success = False
                failed_count = 0
                while not success:
                    if failed_count > max_retries:
                        break

                    success = renderURL(
                        service.get('url'),
                        output,
                        size,
                        headers=headers,
                    )
                    if not success:
                        failed_count += 1

                if not exit:
                    log.error('\t[ee] failed to render: %d', failed_count)
                    continue

                log.debug('\t%10.5f spent to render', (time.time() - s))

                if success:
                    s = time.time()
                    new_file, cropped = handle_image(output)
                    upload(new_file, service, device, size, cropped=cropped)
                    log.debug('\t%10.5f spent to upload', (time.time() - s))

                    # remove output
                    os.remove(output)
                    if os.path.exists(new_file):
                        os.remove(new_file)

                log.debug('\t%10.5f spent', (time.time() - s))

            log.debug('\tdevice: `%s` done', device.get('name'))

        log.debug('< service: `%s` done', service.get('name'))
