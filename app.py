from flask import Flask, render_template, request, redirect, url_for
import whois
import concurrent.futures
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///domains.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database model
class Domain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain_name = db.Column(db.String(255), unique=True, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    payment_period = db.Column(db.Enum('Monthly', 'Yearly'), nullable=False)
    option = db.Column(db.Enum('Buy', 'Sell'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create the database
with app.app_context():
    db.create_all()

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        domain_name = request.form['domain_name']
        price = request.form['price']
        payment_period = request.form['payment_period']
        option = request.form['option']

        new_domain = Domain(
            domain_name=domain_name,
            price=price,
            payment_period=payment_period,
            option=option
        )
        db.session.add(new_domain)
        db.session.commit()

        return redirect(url_for('auction'))

    return render_template('admin.html')

@app.route('/auction')
def auction():
    domains = Domain.query.order_by(Domain.created_at.desc()).all()
    return render_template('auction.html', domains=domains)
app.secret_key = 'eef3rd'  # Needed for session management

EXTENSIONS = ['.com', '.net', '.org', '.info', '.io']

def format_domain(domain_name):
    # If no extension is provided, default to ".com"
    if '.' not in domain_name:
        domain_name += '.com'
    return domain_name

def check_domain_availability(domain_name):
    try:
        domain_info = whois.whois(domain_name)
        if domain_info.status is None or 'No match for' in domain_info.text:
            return True
        return False
    except whois.parser.PywhoisError:
        return True  # Treat any parsing errors as the domain being available
    except Exception as e:
        return False  # Treat other exceptions as the domain being unavailable

def check_multiple_extensions(domain_name_base):
    results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_domain = {executor.submit(check_domain_availability, domain_name_base + ext): ext for ext in EXTENSIONS}
        for future in concurrent.futures.as_completed(future_to_domain):
            ext = future_to_domain[future]
            domain_name = domain_name_base + ext
            try:
                available = future.result()
                results[domain_name] = available
            except Exception as exc:
                results[domain_name] = False
    return results

def get_domain_info(domain_name):
    try:
        domain = whois.whois(domain_name)
        domain_info = {
            'name': domain_name,
            'tld': domain_name.split('.')[-1],
            'registrar': domain.registrar,
            'registrant_country': domain.registrant_country or 'N/A',
            'creation_date': domain.creation_date,
            'expiration_date': domain.expiration_date,
            'last_updated': domain.updated_date if domain.updated_date else ['N/A'],
            'status': domain.status or ['N/A'],
            'dnssec': domain.dnssec or 'N/A',
            'name_servers': domain.name_servers or ['N/A'],
            'registrant': domain.registrant or 'N/A',
            'emails': domain.emails or ['N/A']
        }
    except Exception as e:
        domain_info = {'error': str(e)}
    return domain_info

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    specific_domain_result = None
    if request.method == 'POST':
        domain_name = request.form['domain_name']
        if domain_name:
            domain_name = domain_name.replace(" ", "")  # Remove any spaces
            if '.' in domain_name:
                # User provided a specific domain
                specific_domain_result = {
                    'domain': domain_name,
                    'available': check_domain_availability(domain_name)
                }
            else:
                # User did not provide a specific domain, check multiple extensions
                domain_name_base = domain_name.split('.')[0]  # Remove any existing extension
                results = check_multiple_extensions(domain_name_base)
    return render_template('index.html', results=results, specific_domain_result=specific_domain_result)

@app.route('/domaininfo', methods=['GET', 'POST'])
def domaininfo():
    domain_info = None
    if request.method == 'POST':
        domain_name = request.form.get('domain_name')

        if domain_name:
            domain_name = domain_name.replace(" ", "")  # Remove any spaces
            domain_name = format_domain(domain_name)  # Ensure domain name has a valid extension
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(get_domain_info, domain_name)
                domain_info = future.result()

    return render_template('domaininfo.html', domain_info=domain_info)

if __name__ == '__main__':
    app.run(debug=True)
