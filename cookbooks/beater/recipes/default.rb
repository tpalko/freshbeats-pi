%w{ python-dev python-pip libmysqlclient-dev npm nodejs }.each do |p|
	package p
end

bash "install-requirements" do

	code <<-EOH
		cd /vagrant/webapp
		pip install -r requirements.txt
	EOH

	user "root"
	action :run

end

bash "configure-supervisor" do

	code <<-EOH
		mkdir -p /var/log/supervisor
		mkdir -p /etc/supervisor/conf.d
		echo_supervisord_conf > /etc/supervisor/supervisord.conf
		echo "[include]" >> /etc/supervisor/supervisord.conf
		echo "files = ./conf.d/*.conf" >> /etc/supervisor/supervisord.conf
		cp /vagrant/webapp/deploy/supervisor/* /etc/supervisor/conf.d/
	EOH

	user "root"
	action :run
end

bash "install-nginx-config" do

	code <<-EOH
		cp /vagrant/webapp/deploy/nginx/beater.conf /etc/nginx/sites-available/		
		ln -fs /etc/nginx/sites-available/beater.conf /etc/nginx/sites-enabled/beater.conf
		cp /etc/nginx/uwsgi_params /etc/nginx/sites-enabled/
		rm -f /etc/nginx/sites-enabled/default
		service nginx restart
	EOH

	user "root"
	action :run
	
end

bash "create-mysql-resources" do

	code <<-EOH
		mysql -u root -p -e "create user 'dev'@'localhost' identified by 'dev';"
		mysql -u root -p -e "create user 'dev'@'%' identified by 'dev';"
		mysql -u root -p -e "create database beater character set utf8;"
		mysql -u root -p -e "grant all privileges on beater.* to 'dev'@'localhost';"
		mysql -u root -p -e "grant all privileges on beater.* to 'dev'@'%';"
	EOH

	user "root"
	action :run
end

bash "create-mysql-user" do

	cwd "/vagrant/webapp"

	code <<-EOH
		python manage.py syncdb --noinput
		python manage.py migrate beater
	EOH

	action :run
end