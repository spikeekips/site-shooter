From wernight/phantomjs

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV TERM=xterm
ENV DEBIAN_FRONTEND=noninteractive

USER root
RUN { \
    echo "alias ls='ls --color=auto'"; \
    echo "alias v='ls -al'"; \
    echo "alias a='ls -a'"; \
    echo "set -o vi"; \
} >> ~/.bashrc

RUN apt-get -q update

# set locale
RUN apt-get -q install -y locales
RUN echo en_US.UTF-8 UTF-8 > /etc/locale.gen && locale-gen

RUN apt-get -q install -y build-essential git make python-pip python locales sudo cron python-dev python-six python-pillow

RUN pip -v install --upgrade PyYAML oauth2client google-api-python-client

RUN apt-get -q -y remove python-dev python-pip build-essential git make && \
    apt-get -q -y clean && apt-get -y autoremove && rm -rf /tmp/* /var/lib/apt/lists/*

# USER phantomjs
COPY files/site-shooter.py /opt/site-shooter.py
COPY files/ss /opt/ss
RUN chmod 755 /opt/site-shooter.py

COPY files/renderURL.js /opt
COPY files/*.ttf /usr/share/fonts/truetype/

# cron
#RUN echo '' > /etc/crontab
COPY files/cron /etc/cron.d/site-shooter
COPY files/config.yml /opt/

CMD ["/usr/sbin/cron", "-f", "-L", "15"]

# vim: tw=100000:
