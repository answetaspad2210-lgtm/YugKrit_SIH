from services import auth_service
from services.notification_service import notify
from database.database import db
from database.models import Organization, Notification


def test_notifications_api_returns_only_current_user_data(app, client):
    with app.app_context():
        org_a = Organization(name="Org A", org_type="ULB", status="VERIFIED")
        org_b = Organization(name="Org B", org_type="ULB", status="VERIFIED")
        db.session.add_all([org_a, org_b])
        db.session.flush()

        user_a = auth_service.create_user("User A", "usera@test.local", "Demo@123", "ULB_ADMIN", organization_id=org_a.id)
        user_b = auth_service.create_user("User B", "userb@test.local", "Demo@123", "ULB_ADMIN", organization_id=org_b.id)

        notify(user_a, "For user A", "A message", "/dashboard/citizen/problems/1")
        notify(user_b, "For user B", "B message", "/dashboard/citizen/problems/2")

    login = client.post("/auth/login", data={"email": "usera@test.local", "password": "Demo@123"})
    assert login.status_code in (200, 302)

    response = client.get("/api/notifications")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    titles = [item["title"] for item in payload["data"]]
    assert "For user A" in titles
    assert "For user B" not in titles

    count_response = client.get("/api/notifications/unread-count")
    assert count_response.status_code == 200
    assert count_response.get_json()["data"]["count"] >= 1


def test_notification_mark_read_is_user_scoped(app, client):
    with app.app_context():
        org_a = Organization(name="Org C", org_type="ULB", status="VERIFIED")
        org_b = Organization(name="Org D", org_type="ULB", status="VERIFIED")
        db.session.add_all([org_a, org_b])
        db.session.flush()

        user_a = auth_service.create_user("User C", "userc@test.local", "Demo@123", "ULB_ADMIN", organization_id=org_a.id)
        user_b = auth_service.create_user("User D", "userd@test.local", "Demo@123", "ULB_ADMIN", organization_id=org_b.id)

        note = notify(user_a, "Private", "Only A should see me", "/dashboard/citizen/problems/5")
        other_note = notify(user_b, "Other", "Other user message", "/dashboard/citizen/problems/6")

    with app.app_context():
        other_user_notification_id = Notification.query.filter_by(title="Other").first().id
        own_notification_id = Notification.query.filter_by(title="Private").first().id

    login = client.post("/auth/login", data={"email": "userc@test.local", "password": "Demo@123"})
    assert login.status_code in (200, 302)

    other_user_read = client.post(f"/api/notifications/{other_user_notification_id}/read")
    assert other_user_read.status_code == 404

    my_read = client.post(f"/api/notifications/{own_notification_id}/read")
    assert my_read.status_code == 200
    assert my_read.get_json()["success"] is True

    with app.app_context():
        updated = db.session.get(Notification, own_notification_id)
        assert updated.is_read is True
