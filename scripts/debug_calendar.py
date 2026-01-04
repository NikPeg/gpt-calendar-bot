#!/usr/bin/env python3
"""
Debug script to test Google Calendar API queries.
This script uses the exact same logic as the bot to query Google Calendar
and shows detailed information about what the API returns.

Usage:
    python scripts/debug_calendar.py [service_account.json] [user_email]

    If service_account.json is not provided, it will use:
    scripts/scribo-410009-daa234e02bff.json

    If user_email is not provided, it will use client_email from the service account.

Requirements:
    Install dependencies: pip install -r requirements/requirements.txt
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Check for required dependencies
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print("❌ Error: Missing required dependencies")
    print(f"   {e}")
    print("\n   Please install dependencies:")
    print("   pip install -r requirements/requirements.txt")
    sys.exit(1)

# Add parent directory to path to import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    # Import the CalendarService to use the exact same logic
    from services.calendar_service import CalendarService
except ImportError as e:
    print(f"❌ Error importing CalendarService: {e}")
    print("   Make sure you're running from the project root directory")
    sys.exit(1)


def load_service_account_json(file_path: str) -> str:
    """Load service account JSON from file."""
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subsection(title: str):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---")


def create_delegated_service(service_account_json: str, user_email: str):
    """
    Create a Google Calendar service with domain-wide delegation.

    Args:
        service_account_json: JSON string of service account
        user_email: Email of the user to impersonate

    Returns:
        Google Calendar service object
    """
    credentials_info = json.loads(service_account_json)

    # Create base credentials
    base_credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )

    # Use domain-wide delegation to impersonate the user
    delegated_credentials = base_credentials.with_subject(user_email)

    # Build service with delegated credentials
    return build("calendar", "v3", credentials=delegated_credentials)


def debug_calendar_query(service_account_path: str, user_email: str = None):
    """
    Debug Google Calendar API queries using domain-wide delegation.

    Args:
        service_account_path: Path to service account JSON file
        user_email: User email to access calendar (REQUIRED for domain-wide delegation)
    """
    print_section("Google Calendar API Debug Script (with Domain-Wide Delegation)")

    # Step 1: Load service account JSON
    print_subsection("Step 1: Loading Service Account")
    try:
        service_account_json = load_service_account_json(service_account_path)
        service_account_data = json.loads(service_account_json)
        service_account_email = service_account_data.get("client_email", "")
        print("✅ Service account JSON loaded successfully")
        print(f"   Project ID: {service_account_data.get('project_id')}")
        print(f"   Service Account Email: {service_account_email}")

        # User email is REQUIRED for domain-wide delegation
        if not user_email:
            print("\n   ⚠️  WARNING: No user email provided!")
            print(
                "   The script will test with service account email (will show empty calendar)"
            )
            print("   To see user's events, provide user email as second argument:")
            print(
                f"   python scripts/debug_calendar.py {service_account_path} user@example.com"
            )
            user_email = service_account_email
            use_delegation = False
        else:
            print(f"   ✅ User email provided: {user_email}")
            if user_email != service_account_email:
                print("   ✅ Will use domain-wide delegation to access user's calendar")
                use_delegation = True
            else:
                print("   ⚠️  User email same as service account - no delegation needed")
                use_delegation = False
    except FileNotFoundError:
        print(f"❌ Error: Service account file not found: {service_account_path}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in service account file: {e}")
        return
    except Exception as e:
        print(f"❌ Error loading service account: {e}")
        return

    # Step 2: Initialize service with or without delegation
    print_subsection("Step 2: Initializing Google Calendar Service")
    try:
        if use_delegation:
            print(f"   Creating service with domain-wide delegation for: {user_email}")
            service = create_delegated_service(service_account_json, user_email)
            print("✅ Service initialized with domain-wide delegation")
        else:
            # Use CalendarService for comparison (same as bot)
            calendar_service = CalendarService(service_account_json)
            if not calendar_service.is_configured():
                print("❌ CalendarService is not configured!")
                return
            service = calendar_service.service
            print("✅ Service initialized (without delegation - same as current bot)")
    except Exception as e:
        print(f"❌ Error initializing service: {e}")
        import traceback

        traceback.print_exc()
        return

    # Step 3: Get calendar ID
    print_subsection("Step 3: Getting Calendar ID")
    calendar_id = None
    try:
        # List all available calendars
        print("   Listing all available calendars:")
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])
        print(f"   Found {len(calendars)} calendar(s):")

        primary_calendar = None
        for i, cal in enumerate(calendars, 1):
            cal_id = cal.get("id", "N/A")
            cal_summary = cal.get("summary", "N/A")
            cal_primary = cal.get("primary", False)
            cal_access = cal.get("accessRole", "N/A")
            print(f"   {i}. {cal_summary}")
            print(f"      ID: {cal_id}")
            print(f"      Primary: {cal_primary}")
            print(f"      Access Role: {cal_access}")

            if cal_primary:
                primary_calendar = cal

        # Use primary calendar or first available
        if primary_calendar:
            calendar_id = primary_calendar.get("id")
            print(f"\n   ✅ Using primary calendar: {primary_calendar.get('summary')}")
        elif calendars:
            calendar_id = calendars[0].get("id")
            print(
                f"\n   ✅ Using first available calendar: {calendars[0].get('summary')}"
            )
        else:
            print("❌ No calendars found")
            return

        print(f"   Calendar ID: {calendar_id}")

        # Check if there are shared calendars (important for Gmail users)
        shared_calendars = [
            c
            for c in calendars
            if not c.get("primary", False) and c.get("accessRole") != "owner"
        ]
        if shared_calendars:
            print(f"\n   ℹ️  Found {len(shared_calendars)} shared calendar(s):")
            for i, cal in enumerate(shared_calendars, 1):
                print(
                    f"   {i}. {cal.get('summary', 'N/A')} (Access: {cal.get('accessRole', 'N/A')})"
                )
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error getting calendar ID: {error_msg}")

        # Check if it's a domain-wide delegation error
        if (
            "unauthorized_client" in error_msg.lower()
            or "unauthorized" in error_msg.lower()
        ):
            print("\n   ⚠️  DOMAIN-WIDE DELEGATION ERROR:")
            print(
                "   Domain-wide delegation doesn't work with personal Gmail accounts."
            )
            print("   It only works with Google Workspace (formerly G Suite) accounts.")
            print("\n   💡 SOLUTION FOR GMAIL ACCOUNTS:")
            print(
                "   Since you're using a personal Gmail account, domain-wide delegation won't work."
            )
            print(
                "   Instead, you need to SHARE your Gmail calendar with the service account:"
            )
            print("\n   1. Go to Google Calendar (calendar.google.com)")
            print("   2. Click on 'Settings' (gear icon) → 'Settings'")
            print("   3. Click on 'Share with specific people' (left sidebar)")
            print(f"   4. Click 'Add people' and enter: {service_account_email}")
            print(
                "   5. Give it 'Make changes to events' or 'See all event details' permission"
            )
            print("   6. Click 'Send'")
            print(
                "\n   After sharing, the service account will be able to see your calendar events!"
            )
            print(
                "   Then run this script again - it should find your shared calendar."
            )
            print(
                "\n   Let's try accessing the service account calendar directly (without delegation)..."
            )

            # Fall back to service account calendar (check for shared calendars)
            try:
                print(
                    "\n   Attempting to access calendars via service account (including shared)..."
                )
                calendar_service = CalendarService(service_account_json)
                if calendar_service.is_configured():
                    service = calendar_service.service
                    calendar_list = service.calendarList().list().execute()
                    calendars = calendar_list.get("items", [])

                    if calendars:
                        print(
                            f"   ✅ Found {len(calendars)} calendar(s) accessible to service account:"
                        )
                        for i, cal in enumerate(calendars, 1):
                            cal_id = cal.get("id", "N/A")
                            cal_summary = cal.get("summary", "N/A")
                            cal_primary = cal.get("primary", False)
                            cal_access = cal.get("accessRole", "N/A")
                            cal_background = cal.get("backgroundColor", "")
                            print(f"   {i}. {cal_summary}")
                            print(f"      ID: {cal_id}")
                            print(f"      Primary: {cal_primary}")
                            print(f"      Access Role: {cal_access}")
                            if cal_background:
                                print(f"      Color: {cal_background}")

                        # Look for user's calendar (shared calendar)
                        user_calendar = None
                        for cal in calendars:
                            # Check if this looks like the user's calendar
                            # It might be shared and have the user's email or name
                            summary = cal.get("summary", "").lower()
                            if user_email and (
                                user_email.split("@")[0] in summary
                                or "peganov" in summary
                            ):
                                user_calendar = cal
                                break

                        # If no specific match, look for primary or first non-service-account calendar
                        if not user_calendar:
                            # Try to find primary calendar
                            for cal in calendars:
                                if cal.get("primary", False):
                                    user_calendar = cal
                                    break

                        # If still no match, use first calendar that's not the service account's own
                        if not user_calendar:
                            for cal in calendars:
                                cal_id = cal.get("id", "")
                                # Service account calendar usually has @group.calendar.google.com
                                if (
                                    "@group.calendar.google.com" not in cal_id
                                    or len(calendars) == 1
                                ):
                                    user_calendar = cal
                                    break

                        # Fallback to first calendar
                        if not user_calendar:
                            user_calendar = calendars[0]

                        calendar_id = user_calendar.get("id")
                        print(f"\n   ✅ Using calendar: {user_calendar.get('summary')}")
                        print(f"   Calendar ID: {calendar_id}")

                        # Also try to access user's calendar directly by email (if shared)
                        if user_email and user_email != service_account_email:
                            user_calendar_id = (
                                user_email  # Gmail calendar ID is usually the email
                            )
                            print(
                                f"\n   ℹ️  Also trying to access user's calendar directly by ID: {user_calendar_id}"
                            )
                            try:
                                # Test if we can access it
                                test_result = (
                                    service.calendars()
                                    .get(calendarId=user_calendar_id)
                                    .execute()
                                )
                                print("   ✅ Can access user's calendar directly!")
                                print(
                                    f"   Calendar name: {test_result.get('summary', 'N/A')}"
                                )
                                calendar_id = (
                                    user_calendar_id  # Use the user's calendar instead
                                )
                                print(
                                    f"   ✅ Switching to user's calendar: {calendar_id}"
                                )
                            except Exception as e:
                                print(
                                    f"   ⚠️  Cannot access calendar directly by ID: {e}"
                                )
                                print("   Will use the calendar from the list instead")

                        use_delegation = False  # Switch to non-delegated access
                    else:
                        print("   ❌ No calendars found for service account")
                        print(
                            "   Make sure you've shared your calendar with the service account!"
                        )
                        return
                else:
                    print("   ❌ Could not initialize service")
                    return
            except Exception as e2:
                print(f"   ❌ Error accessing service account calendar: {e2}")
                import traceback

                traceback.print_exc()
                return
        else:
            import traceback

            traceback.print_exc()
            return

    # Step 4: Query events (same logic as bot's list_events)
    print_subsection("Step 4: Querying Events")

    # Use the same parameters as the bot would use
    max_results = 10
    time_min = None  # Will default to now
    time_max = None
    events = []  # Initialize for conclusion section

    print("   Query parameters:")
    print(f"   - Calendar ID: {calendar_id}")
    print(f"   - Max Results: {max_results}")
    print(f"   - Time Min: {time_min or 'Now (default)'}")
    print(f"   - Time Max: {time_max or 'Not set'}")

    try:
        # Build parameters exactly as the bot does
        params = {
            "calendarId": calendar_id,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        # Format timeMin (same logic as bot)
        if time_min:
            # Ensure RFC3339 format
            if "Z" in time_min or "+" in time_min or time_min.count("-") > 2:
                time_min = time_min.replace("+00:00", "Z")
            elif "T" in time_min:
                time_min = time_min + "Z"
            params["timeMin"] = time_min
        else:
            # Default to now (same as bot)
            now = datetime.now(UTC)
            params["timeMin"] = now.isoformat().replace("+00:00", "Z")
            print(f"   - Actual Time Min: {params['timeMin']}")

        if time_max:
            # Ensure RFC3339 format
            if "Z" in time_max or "+" in time_max or time_max.count("-") > 2:
                time_max = time_max.replace("+00:00", "Z")
            elif "T" in time_max:
                time_max = time_max + "Z"
            params["timeMax"] = time_max

        print("\n   Executing API call with parameters:")
        for key, value in params.items():
            print(f"     {key}: {value}")

        # Make the API call
        events_result = service.events().list(**params).execute()

        # Analyze the response
        print("\n   ✅ API call successful!")
        print("\n   Raw API Response:")
        print(f"   - Keys in response: {list(events_result.keys())}")

        events = events_result.get("items", [])
        print(f"   - Number of events returned: {len(events)}")

        # Check for pagination
        if "nextPageToken" in events_result:
            print("   - ⚠️  More events available (nextPageToken present)")

        # Check for time zone
        if "timeZone" in events_result:
            print(f"   - Time Zone: {events_result['timeZone']}")

        # Check for summary
        if "summary" in events_result:
            print(f"   - Summary: {events_result['summary']}")

        # Display events
        if events:
            print(f"\n   📅 Events found ({len(events)}):")
            for i, event in enumerate(events, 1):
                print(f"\n   Event {i}:")
                print(f"     ID: {event.get('id', 'N/A')}")
                print(f"     Summary: {event.get('summary', 'N/A')}")
                print(f"     Status: {event.get('status', 'N/A')}")

                # Start time
                start = event.get("start", {})
                if "dateTime" in start:
                    print(
                        f"     Start: {start.get('dateTime')} (timezone: {start.get('timeZone', 'N/A')})"
                    )
                elif "date" in start:
                    print(f"     Start: {start.get('date')} (all-day event)")

                # End time
                end = event.get("end", {})
                if "dateTime" in end:
                    print(
                        f"     End: {end.get('dateTime')} (timezone: {end.get('timeZone', 'N/A')})"
                    )
                elif "date" in end:
                    print(f"     End: {end.get('date')} (all-day event)")

                # Description
                if "description" in event:
                    desc = event.get("description", "")
                    desc_preview = desc[:50] + "..." if len(desc) > 50 else desc
                    print(f"     Description: {desc_preview}")

                # Location
                if "location" in event:
                    print(f"     Location: {event.get('location')}")

                # Creator
                if "creator" in event:
                    creator = event.get("creator", {})
                    print(f"     Creator: {creator.get('email', 'N/A')}")

                # Organizer
                if "organizer" in event:
                    organizer = event.get("organizer", {})
                    print(f"     Organizer: {organizer.get('email', 'N/A')}")
        else:
            print("\n   ⚠️  No events found!")
            print("   This could mean:")
            print("   - There are no events in the calendar")
            print("   - All events are in the past (before timeMin)")
            print("   - The service account doesn't have access to the calendar")
            print("   - Domain-wide delegation is not set up correctly")

        # Also try querying without timeMin to see all events
        print_subsection("Step 5: Querying All Events (No Time Filter)")
        try:
            params_all = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }

            events_result_all = service.events().list(**params_all).execute()
            events_all = events_result_all.get("items", [])
            print(f"   Found {len(events_all)} events without time filter")

            if events_all and not events:
                print("   ⚠️  IMPORTANT: Events exist but are filtered out by timeMin!")
                print(
                    "   This suggests events are in the past relative to the current time."
                )

            # Also try querying for January 2026 specifically
            print("\n   Querying events for January 2026 (to find tomorrow's event):")
            params_jan = {
                "calendarId": calendar_id,
                "maxResults": 50,
                "singleEvents": True,
                "orderBy": "startTime",
                "timeMin": "2026-01-01T00:00:00Z",
                "timeMax": "2026-01-31T23:59:59Z",
            }
            events_jan = service.events().list(**params_jan).execute().get("items", [])
            print(f"   Found {len(events_jan)} events in January 2026")
            if events_jan:
                print("   📅 Events in January:")
                for i, event in enumerate(events_jan, 1):
                    summary = event.get("summary", "No title")
                    start = event.get("start", {})
                    start_time = start.get("dateTime") or start.get("date", "N/A")
                    print(f"   {i}. {summary} - {start_time}")
        except Exception as e:
            print(f"   ⚠️  Could not query all events: {e}")

    except HttpError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"   Error Code: {e.resp.status}")
        print(
            f"   Error Details: {e.error_details if hasattr(e, 'error_details') else 'N/A'}"
        )
        import traceback

        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error querying events: {e}")
        import traceback

        traceback.print_exc()

    # Final conclusion
    print_section("CONCLUSION")
    print("🔍 Key Findings:")
    print(f"   1. Service account email: {service_account_data.get('client_email')}")
    print(f"   2. User email used: {user_email}")
    print(f"   3. Calendar ID found: {calendar_id}")
    print(f"   4. Events found: {len(events)}")

    if use_delegation:
        if len(events) > 0:
            print("\n   ✅ SUCCESS! Domain-wide delegation is working!")
            print(
                "   The script successfully accessed the user's calendar and found events."
            )
            print("   The bot code can be fixed using the same approach.")
        else:
            print("\n   ⚠️  Domain-wide delegation worked, but no events found.")
            print("   This could mean:")
            print("   - The user's calendar is empty")
            print("   - All events are in the past (filtered by timeMin)")
            print("   - Try querying without timeMin to see all events")
    else:
        if len(events) > 0:
            print("\n   ✅ SUCCESS! Found events in the calendar!")
            print("   The service account can access the calendar (likely shared).")
            print("   The bot should be able to see these events too.")
        else:
            print("\n   ⚠️  PROBLEM IDENTIFIED:")
            if user_email and user_email != service_account_data.get("client_email"):
                print(
                    "   Domain-wide delegation failed (Gmail accounts don't support it)."
                )
                print("   The service account calendar is empty (0 events).")
                print("\n   💡 SOLUTION:")
                print("   Share your Gmail calendar with the service account:")
                print("   1. Go to calendar.google.com")
                print("   2. Settings → Share with specific people")
                print(f"   3. Add: {service_account_email}")
                print("   4. Give 'Make changes to events' permission")
                print("   5. After sharing, run this script again")
            else:
                print(
                    "   The script used the service account's own email (no delegation)."
                )
                print(
                    "   This is the same issue the bot has - it queries the wrong calendar."
                )
                print("\n   💡 TO FIX:")
                print("   Run the script with your actual email address:")
                print(
                    f"   python scripts/debug_calendar.py {service_account_path} your-email@example.com"
                )

    print_section("Debug Complete")


if __name__ == "__main__":
    # Default to the service account file in the scripts directory
    script_dir = Path(__file__).parent
    default_service_account = script_dir / "scribo-410009-daa234e02bff.json"

    # Allow override via command line
    if len(sys.argv) > 1:
        service_account_path = sys.argv[1]
    else:
        service_account_path = str(default_service_account)

    # Optional user email (for domain-wide delegation)
    user_email = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(service_account_path).exists():
        print(f"❌ Error: Service account file not found: {service_account_path}")
        print("\nUsage: python debug_calendar.py [service_account.json] [user_email]")
        sys.exit(1)

    debug_calendar_query(service_account_path, user_email)
