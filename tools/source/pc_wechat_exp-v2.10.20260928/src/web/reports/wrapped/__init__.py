"""Wrapped annual report — Flask blueprint with API routes."""
from flask import Blueprint, request, jsonify, current_app

wrapped_bp = Blueprint('wrapped', __name__, url_prefix='/api/wrapped')


def _get_account():
    return request.args.get('account') or None


def _get_year():
    y = request.args.get('year', type=int)
    if y is None:
        return None
    if not (2000 <= y <= 2099):
        return None
    return y


def _get_refresh():
    return request.args.get('refresh', '').lower() in ('1', 'true', 'yes')


@wrapped_bp.route('/annual')
def annual():
    """Full wrapped annual response — all cards at once."""
    from .service import build_wrapped_annual_response
    try:
        result = build_wrapped_annual_response(
            account=_get_account(),
            year=_get_year(),
            refresh=_get_refresh(),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@wrapped_bp.route('/annual/meta')
def annual_meta():
    """Lightweight manifest — card ids/titles/scopes for the frontend deck."""
    from .service import build_wrapped_annual_meta
    try:
        result = build_wrapped_annual_meta(
            account=_get_account(),
            year=_get_year(),
            refresh=_get_refresh(),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@wrapped_bp.route('/annual/cards/<int:card_id>')
def annual_card(card_id):
    """Single card (page) on-demand — supports lazy loading."""
    from .service import build_wrapped_annual_card
    try:
        result = build_wrapped_annual_card(
            account=_get_account(),
            year=_get_year(),
            card_id=card_id,
            refresh=_get_refresh(),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
