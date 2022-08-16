# keytracker
KeyForge game tracker software

Installation instructions I used on Ubuntu on Windows

1. Install and setup Ubuntu on Windows: https://ubuntu.com/tutorials/ubuntu-on-windows
2. Install python3 and some other packages: sudo apt-get install python3 python3-venv python-dev libmysqlclient-dev
3. Install and start mysql server, and create a user with a db.
4. Download this git repo: wget https://github.com/avandever/keytracker/archive/refs/heads/main.zip
5. Unzip the repo: unzip main.zip
6. cd keytracker-main
7. Set up the virtual environment: python3 -m venv venv
8. Activate the virtual environment: source venv/bin/activate
9. Install modules: pip3 install . gunicorn
10. Run the server: gunicorn -w 4 "keytracker.server:app"
11. Run the client: keytracker/client.py
