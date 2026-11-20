import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def batch_dict(b):
    return {'id': b.id, 'name': b.name, 'source': b.source, 'rows': b.rows, 'checksum': b.checksum, 'created_at': b.created_at}
def cert_dict(c):
    return {'id': c.id, 'cert_no': c.cert_no, 'issuer': c.issuer, 'month': c.month,
            'total_kwh': c.total_kwh, 'reserved_kwh': round(c.reserved_kwh, 3), 'issued_kwh': round(c.issued_kwh, 3),
            'remaining_kwh': round(c.total_kwh - c.reserved_kwh - c.issued_kwh, 3),
            'status': c.status, 'revoke_effective_at': c.revoke_effective_at, 'revoked_at': c.revoked_at, 'created_at': c.created_at}
def claim_dict(c, cert_no='', line_code='', customer_name='', reissue_state=''):
    return {'id': c.id, 'certificate_id': c.certificate_id, 'cert_no': cert_no, 'line_id': c.line_id,
            'line_code': line_code, 'customer_name': customer_name, 'month': c.month, 'kwh': c.kwh,
            'kind': c.kind, 'status': c.status, 'replaces_id': c.replaces_id, 'root_id': c.root_id,
            'note': c.note, 'reissue_state': reissue_state, 'created_at': c.created_at, 'issued_at': c.issued_at}
def plan_dict(p, customer_name=''):
    return {'id': p.id, 'name': p.name, 'customer_id': p.customer_id, 'customer_name': customer_name,
            'month': p.month, 'destination': p.destination, 'interval_seconds': p.interval_seconds,
            'next_run': p.next_run, 'enabled': p.enabled}
def delivery_dict(d):
    return {k: getattr(d, k) for k in ['id', 'plan_id', 'created_at', 'checksum', 'filename', 'destination']}
