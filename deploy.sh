#!/bin/bash
# pub_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDDew7+vyyLXQyk4oZ+zYr1a3f9zaJQ+htfcmREpVznia5UW3u1JUHlQEeXJ5cD78Gu4BslE6hzrMWaVqv85dKhZWgWIEL9iaIgq/W1qVpDPQBruOUhjyvmzrReuXXn1N2V07CKE8UHwE/PrLbf0f7WH5e0MHfrgP5c54oqrxdm0neJ/3Uoe++8CL0RZLrfnlF2Vnf+fWB/gg36EGvT63EVWcpjFBQmyusl1Kg4t7x8Tym75uO5/tZpq1cWvmwZXb1LETrF5h2ct0KOqGF2nE6EMdnNpyelSGOwOlc0jVIKwk78aMR0wHnzR30Na6THhxSwit6ad1GCzYMTKJKnmcYuJZk/XHylagjsPo7cbDv1IMSCyzvh4Bg49jhgeNGJSXF9r6D/8DLJn0KZDrd2cTzmRVQuaNKH1nP7WGgRg6N505oupMSsRPIA1eS7mUd0kxkyxa77fHvGAOnMJVJb89atYx4qUxwFpwzrXBZWvmr876NpB5MfuTMHYpCkTcWmV6zajc3b11nI/cy+RGb0vAnvtsLtOnxM+LzdUMD5Ao7OaRDfAnfb47JFVFBRoXKOxbmhraRLivb4fCQgUP5s7AvhFuM5GiHhKHZEf+Qfem9s41mjavcQHTdtZ1kmULwizM2hzq58MPE7K71wPs/ZlLb9zP4rhqNqlM70LfXx0H7Xlw== theoziran@gmail.com"
# ssh $TARGET_USER@$TARGET_HOST bash -c "'
# echo $pub_key >> ~/.ssh/authorized_keys
# '"
# exit 1
send_message () {
  curl -X POST https://api.telegram.org/bot${TELEGRAM_TOKEN_DEPLOY}/sendMessage --data "chat_id=-255761120&text=${1}"
}

DB_NAME=game.db
LOGGING_PATH=/var/log/secreth.log
echo "TELEGRAM_TOKEN=$TELEGRAM_TOKEN_DEPLOY
ADMIN_USER=$ADMIN_USER_DEPLOY
STATS_FILE=$TARGET_DIR/stats.json
SQLITE_FILE=$TARGET_DIR/$DB_NAME
LOGGING_PATH=$LOGGING_PATH
SPECTATORS_GROUP=-1001271387673
SPECTATORS_JOIN_URL=https://t.me/joinchat/GnbyqBFMsuB1ENvP8coGMQ
" > .env

echo "[program:secreth]
directory=$TARGET_DIR
user=$TARGET_USER
command=python3 MainController.py
autostart=true
autorestart=true
stderr_logfile=/var/log/secreth.err.log
stdout_logfile=/var/log/secreth.out.log" > "secreth.conf"

send_message "Deploy started. Locating Man in the High Castle."
ssh $TARGET_USER@$TARGET_HOST "[ -d $TARGET_DIR ] || mkdir $TARGET_DIR"
scp -r * $TARGET_USER@$TARGET_HOST:$TARGET_DIR
scp .env $TARGET_USER@$TARGET_HOST:$TARGET_DIR
# Provision
# sudo apt-get update
# sudo apt-get install supervisor sqlite3 python3-pip -y
# sudo apt-get autoremove -y
ssh $TARGET_USER@$TARGET_HOST bash -c "'
    cd $TARGET_DIR
    if [ ! -f $TARGET_DIR/$DB_NAME ];
    then
        sqlite3 -init $TARGET_DIR/game.sql $DB_NAME
    fi
    sudo chmod 0777 $LOGGING_PATH
    sudo apt-get -y install libssl-dev
    pip3 install -r requirements.txt
    sudo cp secreth.conf /etc/supervisor/conf.d
    sudo supervisorctl reload
    sleep 3
    sudo supervisorctl stop secreth
    sleep 3
    sudo supervisorctl start secreth
'"
send_message "Deploy finished. Enjoy the game."
