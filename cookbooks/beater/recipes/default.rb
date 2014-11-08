%w{ python-dev python-pip mysql-client-5.6 libmysqlclient-dev nginx }.each do |p|
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
		cp /vagrant/webapp/deploy/supervisor/* /etc/supervisor/conf.d/
	EOH

	user "root"
	action :run
end

bash "install-nginx-config" do

	code <<-EOH
		cp /vagrant/webapp/deploy/beater.conf /etc/nginx/sites-available
		ln -fs /etc/nginx/sites-available/beater.conf /etc/nginx/sites-enabled/beater.conf
		rm -f /etc/nginx/sites-enabled/default
		service nginx restart
	EOH

	user "root"
	action :run
	
end