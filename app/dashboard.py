
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path


router = APIRouter(tags=["dashboard"])
template_dir = Path(__file__).parent / "templates"
print(f"📁 Template directory: {template_dir}")
print(f"✓ Exists: {template_dir.exists()}")

if template_dir.exists():
    print(f"📄 Files in templates: {list(template_dir.iterdir())}")

templates = Jinja2Templates(directory=str(template_dir))

@router.get("/")
def dashboard_home():
    # Get conversation data
    from app.main import claude_service
    
    conversations = []
    return {
    "message": "Dashboard migrated to database - update in progress",
    "status": "ok"
}
    
    total_users = len(conversations)
    
    # Build HTML manually (no templates)
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GlowBot Dashboard</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            
            .header {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                margin-bottom: 30px;
            }}
            
            .header h1 {{
                color: #667eea;
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            
            .stat-card {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                margin-top: 20px;
            }}
            
            .stat-card h3 {{
                font-size: 2.5em;
                margin-bottom: 5px;
            }}
            
            .conversations {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            
            .conversation-card {{
                border: 2px solid #e0e0e0;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 15px;
                transition: all 0.3s;
                cursor: pointer;
            }}
            
            .conversation-card:hover {{
                border-color: #667eea;
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.2);
                transform: translateY(-2px);
            }}
            
            .user-id {{
                font-weight: bold;
                color: #667eea;
                font-size: 1.2em;
                margin-bottom: 10px;
            }}
            
            .badge {{
                display: inline-block;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.85em;
                margin-right: 8px;
                margin-top: 5px;
            }}
            
            .badge-state {{
                background: #667eea;
                color: white;
            }}
            
            .badge-language {{
                background: #f0f0f0;
                color: #333;
            }}
            
            .badge-skin {{
                background: #e3f2fd;
                color: #1976d2;
            }}
            
            .badge-concern {{
                background: #fff3e0;
                color: #f57c00;
            }}
            
            .empty-state {{
                text-align: center;
                padding: 60px 20px;
                color: #999;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌟 GlowBot Dashboard</h1>
                <p>Monitor your skincare consultations</p>
                
                <div class="stat-card">
                    <h3>{total_users}</h3>
                    <p>Total Conversations</p>
                </div>
            </div>
            
            <div class="conversations">
                <h2>Active Conversations</h2>
    """
    
    # Add conversation cards
    if conversations:
        for conv in conversations:
            concerns_html = "".join([
                f'<span class="badge badge-concern">{concern}</span>'
                for concern in conv['concerns']
            ])
            
            skin_badge = ""
            if conv['skin_type'] != "Unknown":
                skin_badge = f'<span class="badge badge-skin">{conv["skin_type"]}</span>'
            
            html += f"""
                <div class="conversation-card" onclick="window.location.href='/dashboard/user/{conv["user_id"]}'">
                    <div class="user-id">👤 {conv["user_id"]}</div>
                    <div>
                        <span class="badge badge-state">{conv["state"]}</span>
                        <span class="badge badge-language">{conv["language"].upper()}</span>
                        {skin_badge}
                        {concerns_html}
                    </div>
                </div>
            """
    else:
        html += """
                <div class="empty-state">
                    <h2>No conversations yet</h2>
                    <p>Start chatting with GlowBot on WhatsApp to see conversations here!</p>
                </div>
        """
    
    html += """
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(html)

# Add this test route
@router.get("/test-template")
def test_template(request: Request):
    """Test if templates are working"""
    try:
        return templates.TemplateResponse(
            "test.html",
            {
                "request": request,  # IMPORTANT: Must pass request
                "name": "GlowBot",
                "count": 5
            }
        )
    except Exception as e:
        return HTMLResponse(f"<h1>Template Error</h1><pre>{str(e)}</pre>")

@router.get("/user/{user_id}")
def user_detail(user_id: str):
    from app.main import claude_service
    
    context = claude_service.user_contexts.get(user_id)
    
    if not context:
        return HTMLResponse("<h1>User not found</h1>", status_code=404)
    
    # Get conversation history
    history = claude_service._message_history.get(user_id, [])
    
    # Build concerns list
    concerns_list = ", ".join(context.skin_profile.concerns) if context.skin_profile.concerns else "Not specified"
    
    # Build history HTML
    history_html = ""
    if history:
        for msg in history:
            msg_class = "message-user" if msg["role"] == "user" else "message-assistant"
            history_html += f"""
                <div class="message {msg_class}">
                    <div class="message-role">{msg["role"].upper()}</div>
                    <div>{msg["content"]}</div>
                </div>
            """
    else:
        history_html = '<p style="color: #999;">No conversation history yet</p>'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>User: {user_id}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            
            .back-button {{
                display: inline-block;
                padding: 10px 20px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 8px;
                margin-bottom: 20px;
                font-weight: bold;
            }}
            
            .back-button:hover {{
                background: #f5f5f5;
            }}
            
            .card {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                margin-bottom: 20px;
            }}
            
            h1 {{
                color: #667eea;
                margin-bottom: 20px;
            }}
            
            h2 {{
                color: #333;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #e0e0e0;
            }}
            
            .info-row {{
                display: flex;
                padding: 12px 0;
                border-bottom: 1px solid #f0f0f0;
            }}
            
            .info-label {{
                font-weight: bold;
                color: #667eea;
                width: 200px;
            }}
            
            .info-value {{
                flex: 1;
            }}
            
            .message {{
                padding: 15px;
                margin: 10px 0;
                border-radius: 10px;
            }}
            
            .message-user {{
                background: #e3f2fd;
                margin-left: 40px;
            }}
            
            .message-assistant {{
                background: #f3e5f5;
                margin-right: 40px;
            }}
            
            .message-role {{
                font-weight: bold;
                margin-bottom: 5px;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/dashboard" class="back-button">← Back to Dashboard</a>
            
            <div class="card">
                <h1>👤 User Details</h1>
                
                <div class="info-row">
                    <div class="info-label">User ID</div>
                    <div class="info-value">{user_id}</div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Current State</div>
                    <div class="info-value">{context.state.value}</div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Language</div>
                    <div class="info-value">{context.language.upper()}</div>
                </div>
            </div>
            
            <div class="card">
                <h2>Skin Profile</h2>
                
                <div class="info-row">
                    <div class="info-label">Skin Type</div>
                    <div class="info-value">{context.skin_profile.skin_type or 'Not specified'}</div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Concerns</div>
                    <div class="info-value">{concerns_list}</div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Sun Exposure</div>
                    <div class="info-value">{context.skin_profile.sun_exposure or 'Not specified'}</div>
                </div>
            </div>
            
            <div class="card">
                <h2>Conversation History</h2>
                {history_html}
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(html)