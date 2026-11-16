from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import pandas as pd
import io

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    is_favorite = db.Column(db.Boolean, default=False)
    methods = db.relationship('ContactMethod', backref='contact', cascade='all, delete-orphan')

class ContactMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    type = db.Column(db.String(20))
    value = db.Column(db.String(100))

with app.app_context():
    db.create_all()

def contact_to_dict(contact):
    return {
        'id': contact.id,
        'name': contact.name,
        'is_favorite': contact.is_favorite,
        'methods': [{'type': m.type, 'value': m.value} for m in contact.methods]
    }

@app.route('/contacts', methods=['GET'])
def get_contacts():
    contacts = Contact.query.all()
    return jsonify([contact_to_dict(c) for c in contacts])

@app.route('/contacts', methods=['POST'])
def add_contact():
    data = request.json
    new_contact = Contact(name=data['name'])
    for m in data.get('methods', []):
        new_method = ContactMethod(type=m['type'], value=m['value'])
        new_contact.methods.append(new_method)
    db.session.add(new_contact)
    db.session.commit()
    return jsonify(contact_to_dict(new_contact)), 201

@app.route('/contacts/<int:id>/favorite', methods=['POST'])
def toggle_favorite(id):
    contact = Contact.query.get_or_404(id)
    contact.is_favorite = not contact.is_favorite
    db.session.commit()
    return jsonify(contact_to_dict(contact))

@app.route('/contacts/<int:id>', methods=['DELETE'])
def delete_contact(id):
    contact = Contact.query.get_or_404(id)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({'message': 'Deleted'})

@app.route('/export', methods=['GET'])
def export_excel():
    contacts = Contact.query.all()
    data = []
    for c in contacts:
        row = {'姓名': c.name, '是否收藏': '是' if c.is_favorite else '否'}
        for m in c.methods:
            row[m.type] = m.value
        data.append(row)
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    
    return send_file(output, download_name="contacts.xlsx", as_attachment=True)

@app.route('/import', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    
    try:
        df = pd.read_excel(file)
        for index, row in df.iterrows():
            name = row['姓名']
            if pd.isna(name): continue
            
            new_contact = Contact(name=str(name), is_favorite=(row.get('是否收藏') == '是'))
            
            for col in df.columns:
                if col not in ['姓名', '是否收藏'] and not pd.isna(row[col]):
                    method = ContactMethod(type=col, value=str(row[col]))
                    new_contact.methods.append(method)
            
            db.session.add(new_contact)
        db.session.commit()
        return jsonify({'message': 'Import successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)