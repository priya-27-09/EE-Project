/**
 * AI Civic Guardian — Centralized Multilingual UI Translation Engine
 * Supported Languages: English (en), Tamil (ta), Hindi (hi)
 * Zero fake translations. Preserves citizen original text and canonical identifiers.
 */

const I18N_DATA = {
  // ==========================================
  // ENGLISH (en)
  // ==========================================
  en: {
    // Brand & Navigation
    app_name: "AI Civic Guardian",
    brand_name: "AI Civic Guardian",
    brand_tagline: "Civic Grievance Redressal",
    welcome: "Welcome",
    home: "Home",
    dashboard: "My Dashboard",
    login: "Login",
    register: "Register",
    logout: "Logout",
    profile: "Profile",
    complaint: "Complaint",
    complaint_id: "Complaint ID",
    issue_type: "Issue Category",
    description: "Description",
    location: "Location",
    upload_image: "Take / Upload Photo",
    review: "Review",
    track_complaint: "Track Complaint",
    ai_processing: "Analyzing evidence with YOLO neural network...",
    review_ai_result: "Citizen Review: AI pre-selected this issue. You can confirm or override it below.",
    department_assigned: "Department Assigned",
    report_problem: "Report a Problem",
    select_language: "Select Language",

    // General Controls
    submit: "Submit",
    cancel: "Cancel",
    back: "Back",
    next: "Next",
    previous: "Previous",
    save: "Save",
    close: "Close",
    confirm: "Confirm",
    continue: "Continue",
    loading: "Loading...",
    error: "Error",
    success: "Success",
    refresh: "Refresh",
    view_details: "View Details",
    remove: "Remove",

    // Landing / Hero
    hero_title: "Report Civic Problems Quickly and Easily",
    hero_sub: "Help improve your community by lodging municipal grievances directly with civic authorities.",
    how_it_works: "How AI Civic Guardian Works",
    step1_hero: "Upload a Photo",
    step1_hero_desc: "Capture or upload photo/video evidence of the issue directly from your mobile phone or computer.",
    step2_hero: "Add Location",
    step2_hero_desc: "Use automatic browser GPS or specify coordinates so field teams can pinpoint the location.",
    step3_hero: "Describe the Issue",
    step3_hero_desc: "Provide details in your preferred language to help teams prioritize.",
    step4_hero: "Track Resolution",
    step4_hero_desc: "Receive an official tracking ID to monitor department assignment and resolution.",

    // Dashboard
    welcome_citizen: "Welcome",
    my_complaints: "My Complaints",
    no_complaints: "You have not lodged any complaints yet.",
    no_complaints_sub: "Click 'Report a Problem' to register your first grievance.",
    manage_monitor_sub: "Manage and monitor all your submitted civic grievances.",
    routing_in_progress: "Routing In Progress",

    // Complaint Tracking / Detail
    grievance_tracking_num: "Grievance Tracking Number",
    grievance_description: "Grievance Description",
    assigned_department: "Assigned Department",
    gps_coordinates: "GPS Coordinates",
    logged_at: "Logged At",
    attached_evidence: "Attached Evidence",
    no_evidence_notice: "No photographic or video evidence attached to this complaint.",
    status_history_timeline: "Status History Timeline",
    back_to_dashboard: "Back to Dashboard",
    copy_id: "Copy Complaint ID",

    // Auth Pages
    citizen_login: "Citizen Login",
    citizen_login_sub: "Access your citizen portal to lodge and track civic complaints.",
    citizen_register: "Citizen Registration",
    citizen_register_sub: "Create your citizen account to lodge and track civic complaints.",
    email_address: "Email Address",
    password: "Password",
    confirm_password: "Confirm Password",
    full_name: "Full Name",
    preferred_comm_lang: "Preferred Communication Language",
    dont_have_account: "Don't have an account yet?",
    already_have_account: "Already have an account?",
    register_here: "Register here",
    login_here: "Log in here",
    log_in_btn: "Log In",
    register_btn: "Register as Citizen",

    // Wizard Stepper
    wizard_step_1: "Evidence",
    wizard_step_2: "Location",
    wizard_step_3: "Description",
    wizard_step_4: "Issue",
    wizard_step_5: "Review",

    // Wizard Step 1: Evidence
    wizard_step1_title: "How would you like to report the problem?",
    wizard_step1_sub: "Upload photographic, video, or voice evidence to help field teams quickly locate and verify the issue.",
    take_upload_photo: "Take / Upload Photo",
    upload_video: "Upload Video",
    record_voice: "Record / Upload Voice",
    describe_with_text: "Describe with Text",
    proceed_no_media: "Proceed without media file",
    continue_to_location: "Continue to Location",

    // Wizard Step 2: Location
    wizard_step2_title: "Where is the problem?",
    wizard_step2_sub: "Precise location helps municipal field inspectors arrive at the exact spot.",
    use_current_location: "Use My Current Location",
    gps_click_hint: "Click to detect coordinates via your device's browser GPS.",
    or_enter_coords: "— OR ENTER COORDINATES MANUALLY (OPTIONAL) —",
    latitude_label: "Latitude",
    longitude_label: "Longitude",
    continue_to_description: "Continue to Description",

    // Wizard Step 3: Description
    wizard_step3_title: "What is the problem?",
    wizard_step3_sub: "Explain the issue so the civic department understands its urgency.",
    lang_for_description: "Language for Description",
    description_label: "Description (Optional if evidence provided)",
    description_placeholder: "e.g. Large pothole near the road junction causing danger to vehicles...",
    continue_to_issue: "Continue to Issue Type",

    // Wizard Step 4: Issue & AI
    wizard_step4_title: "Civic Issue Classification",
    wizard_step4_sub: "AI-assisted detection from your uploaded evidence or manual category selection.",
    ai_status_notice: "Upload a photo for automatic category detection and department routing.",
    citizen_notice_title: "Citizen Notice:",
    dev_fallback_label: "Citizen Notice:",
    auto_assigned_dept: "Automatically Assigned Department",
    ai_analyzing_evidence: "Analyzing evidence with YOLO neural network...",
    ai_validating_raster: "Validating image raster and executing deep learning inference",
    ai_detection: "YOLO AI Detection Active",
    detected_issue: "Detected Issue",
    confidence: "Confidence",
    severity: "Severity",
    department: "Assigned Department",
    ai_citizen_review: "Citizen Review: The AI model has pre-selected this civic issue. You can confirm or override it below.",
    ai_multiple_objects: "Multiple Objects Detected",
    ai_model_not_available: "Image uploaded successfully. Please confirm the issue category to continue.",
    no_detection: "No Civic Issue Detected: The AI model analyzed your image but did not detect a recognized civic hazard with sufficient confidence. Please choose the appropriate category manually below.",
    inference_failed: "AI Processing Error: Unable to process image. You may select the category manually below.",
    select_confirm_category: "Select / Confirm Category",
    click_choose_override: "Click to choose or override",
    continue_to_review: "Continue to Review",

    // Wizard Step 5: Review & Duplicates
    wizard_step5_title: "Review & Submit Complaint",
    wizard_step5_sub: "Verify your complaint details before submitting to municipal authorities.",
    review_issue_category: "Issue Category:",
    review_assigned_dept: "Assigned Dept:",
    review_ai_class: "AI Classification:",
    review_severity_level: "Severity Level:",
    review_location: "Location:",
    review_description: "Description:",
    review_evidence: "Evidence File:",
    routing_dispatch_notice: "Your grievance will be automatically dispatched to the verified municipal department.",
    submit_complaint: "Submit Complaint",
    complaint_submitted: "Complaint Submitted Successfully",

    // Duplicate Warnings
    checking_duplicates: "Checking for similar existing complaints...",
    possible_duplicate: "Possible Duplicate Complaint Detected",
    similar_complaint_found: "A similar complaint in this vicinity has already been reported recently.",
    continue_anyway: "Continue Anyway & Submit",
    view_existing_complaint: "View Existing Complaint",
    distance: "Distance",
    similarity: "Similarity",
    duplicate_reason: "Reason",

    // Statuses
    submitted: "Submitted",
    in_review: "In Review",
    assigned: "Department Assigned",
    in_progress: "In Progress",
    resolved: "Resolved",
    rejected: "Rejected",
    ai_verified: "AI Verified",
    needs_human_review: "Needs Human Review",

    // Resolution Verification
    resolution_verification: "Resolution Evidence Verification",
    before_evidence: "Before / Original Evidence",
    after_evidence: "After / Resolution Evidence",
    verification_status: "Verification Status",
    verification_score: "Verification Score",
    verification_reason: "Analysis Reason",
    human_review_required: "Human Review Required",
    run_verification: "Run Verification",
    review_result: "Review Result",
    approve: "Approve Resolution",
    reject: "Reject Resolution",
    verification_not_available: "Verification Not Available",
    pending_verification: "Pending Verification",
    verification_failed: "Verification Failed",
    resolution_evidence: "Resolution Evidence",
    visual_comparison: "Visual Evidence Comparison",

    // Blockchain Integrity
    blockchain: "Blockchain",
    blockchain_status: "Blockchain Status",
    blockchain_confirmed: "Blockchain Confirmed",
    blockchain_pending: "Blockchain Pending",
    blockchain_failed: "Blockchain Failed",
    blockchain_unavailable: "Blockchain Unavailable",
    blockchain_not_configured: "Blockchain Not Configured",
    integrity_record: "Integrity Record",
    transaction_hash: "Transaction Hash",
    block_number: "Block Number",
    verify_integrity: "Verify Integrity",
    retry_blockchain: "Retry Blockchain",

    // Chatbot & Knowledge Base (Steps 11 + 12)
    civic_assistant: "Civic AI Assistant",
    knowledge_base: "Knowledge Base",
    civic_conversations: "Civic Conversations",
    new_chat: "+ New Chat",
    sources: "Official Sources",
    ask_question: "Ask a civic question...",
    rebuild_index: "Rebuild FAISS Index",
    document_uploaded: "Document Uploaded Successfully",
    retrieval_success: "Grounded Retrieval Active",
    no_relevant_context: "No direct match in municipal guidelines",

    // Severities
    low: "Low",
    medium: "Medium",
    high: "High",
    critical: "Critical",

    // Step 13 & 14 Citizen Dashboard & Tracking
    welcome_prefix: "Welcome",
    citizen_welcome_desc: "Report civic problems easily. Our system helps identify the issue, determine severity, and route your complaint to the appropriate department.",
    action_report_title: "Report a Problem",
    action_report_desc: "Upload a photo, video, voice, or text to lodge a new complaint.",
    action_complaints_title: "My Complaints",
    action_complaints_desc: "View all grievances submitted by your account.",
    action_track_title: "Track Complaint",
    action_track_desc: "Track complaint resolution status, timeline, and assigned department.",
    action_assistant_title: "Civic Assistant",
    action_assistant_desc: "Ask civic and government procedure questions to our grounded AI assistant.",
    get_started: "Start Report →",
    view_all: "View Grievances ↓",
    track_now: "Track Status →",
    ask_assistant: "Ask Assistant →",
    complaint_summary_heading: "Grievance Summary",
    stat_total_complaints: "Total Complaints",
    stat_total_sub: "All logged grievances",
    stat_submitted: "Submitted",
    stat_submitted_sub: "Awaiting verification/dispatch",
    stat_in_progress: "In Progress",
    stat_inprogress_sub: "Under active field repair",
    stat_resolved: "Resolved",
    stat_resolved_sub: "Verified and closed",
    recent_complaints_heading: "My Recent Complaints",
    recent_complaints_sub: "Official real-time status of grievances submitted by your account.",
    no_complaints_title: "No complaints submitted yet.",
    report_first_problem: "Report Your First Problem",
    track_grievance_title: "Track Your Civic Grievance",
    track_grievance_sub: "Enter your official grievance tracking number (format: CG-YYYY-XXXXXX) to monitor resolution progress, department assignment, and milestone updates.",
    workflow_progress: "Resolution Workflow Progress",
    profile_title: "Citizen Profile",
    profile_sub: "Manage your personal details and preferred communication language for official civic notifications.",
    full_name: "Full Name",
    preferred_language: "Preferred Language",
    portal_role: "Account Role",
    member_since: "Member Since",
    save_changes: "Save Profile Changes",
    resolution_report_heading: "Official Grievance Resolution Report",
    resolution_report_sub: "This civic grievance has been officially resolved and verified by the designated municipal department.",
    resolution_remarks: "Officer Resolution Remarks",

    // Errors
    invalid_file: "Invalid or corrupted file uploaded.",
    invalid_location: "Invalid geographic coordinates provided.",
    unauthorized: "You must be logged in to perform this action.",
    network_error: "Network communication failure. Please check your connection.",
    server_error: "An internal server error occurred.",
    required_field: "This field is required.",
  },

  // ==========================================
  // TAMIL (ta)
  // ==========================================
  ta: {
    // Brand & Navigation
    app_name: "AI சிவிக் கார்டியன்",
    brand_name: "AI சிவிக் கார்டியன்",
    brand_tagline: "குடிமக்கள் குறைதீர்ப்பு தளம்",
    welcome: "வரவேற்கிறோம்",
    home: "முகப்பு",
    dashboard: "எனது முகப்பு",
    login: "உள்நுழைக",
    register: "பதிவு செய்க",
    logout: "வெளியேறுக",
    profile: "சுயவிவரம்",
    complaint: "புகார்",
    complaint_id: "புகார் எண்",
    issue_type: "பிரச்சனை வகை",
    description: "விளக்கம்",
    location: "இடம்",
    upload_image: "புகைப்படம் எடுக்க / பதிவேற்ற",
    review: "சரிபார்த்தல்",
    track_complaint: "புகாரை பின்தொடரவும்",
    ai_processing: "YOLO நரம்பியல் வலைப்பின்னல் மூலம் படம் ஆராயப்படுகிறது...",
    review_ai_result: "குடிமக்கள் ஆய்வு: AI இந்த சிக்கலைத் தேர்ந்தெடுத்துள்ளது. நீங்கள் உறுதிப்படுத்தலாம் அல்லது மாற்றலாம்.",
    department_assigned: "துறை ஒதுக்கப்பட்டது",
    report_problem: "புகார் பதிவு செய்க",
    select_language: "மொழியைத் தேர்ந்தெடுக்கவும்",

    // General Controls
    submit: "சமர்ப்பிக்கவும்",
    cancel: "ரத்து செய்க",
    back: "பின்செல்க",
    next: "அடுத்து",
    previous: "முந்தைய",
    save: "சேமிக்கவும்",
    close: "மூடுக",
    confirm: "உறுதிப்படுத்துக",
    continue: "தொடரவும்",
    loading: "ஏற்றப்படுகிறது...",
    error: "பிழை",
    success: "வெற்றி",
    refresh: "புதுப்பிக்கவும்",
    view_details: "விவரங்களைக் காண்க",
    remove: "நீக்கு",

    // Landing / Hero
    hero_title: "குடிமைப் பிரச்சனைகளை எளிதாகப் பதிவு செய்யுங்கள்",
    hero_sub: "உங்கள் பகுதியில் உள்ள நகராட்சி சிக்கல்களை நேரடியாக மாநகராட்சி அதிகாரிகளுக்குத் தெரியப்படுத்துங்கள்.",
    how_it_works: "AI சிவிக் கார்டியன் எவ்வாறு செயல்படுகிறது",
    step1_hero: "புகைப்படம் பதிவேற்றவும்",
    step1_hero_desc: "சிக்கலின் புகைப்படம் அல்லது வீடியோ ஆதாரத்தைப் பகிரவும்.",
    step2_hero: "இடத்தைக் குறிப்பிடவும்",
    step2_hero_desc: "GPS அல்லது முகவரியைப் பயன்படுத்தவும்.",
    step3_hero: "விவரங்களை உள்ளிடவும்",
    step3_hero_desc: "உங்கள் தாய்மொழியில் பிரச்சனையை விவரிக்கவும்.",
    step4_hero: "தீர்வை கண்காணிக்கவும்",
    step4_hero_desc: "புகாரின் நிலையை உடனுக்குடன் தெரிந்துகொள்ளுங்கள்.",

    // Dashboard
    welcome_citizen: "வரவேற்கிறோம்",
    my_complaints: "எனது புகார்கள்",
    no_complaints: "நீங்கள் இதுவரை எந்தப் புகாரும் பதிவு செய்யவில்லை.",
    no_complaints_sub: "உங்கள் முதல் புகாரைப் பதிவு செய்ய 'புகார் பதிவு செய்க' என்பதைக் கிளிக் செய்யவும்.",
    manage_monitor_sub: "உங்கள் அனைத்து நகராட்சி புகார்களையும் எளிதாக நிர்வகித்து கண்காணிக்கவும்.",
    routing_in_progress: "துறை ஒதுக்கீடு பரிசீலனையில் உள்ளது",

    // Complaint Tracking / Detail
    grievance_tracking_num: "புகார் கண்காணிப்பு எண்",
    grievance_description: "புகார் விளக்கம்",
    assigned_department: "ஒதுக்கப்பட்ட துறை",
    gps_coordinates: "புவியியல் ஆயத்தொலைவுகள்",
    logged_at: "பதிவு செய்யப்பட்ட நேரம்",
    attached_evidence: "இணைக்கப்பட்ட ஆதாரம்",
    no_evidence_notice: "இந்தப் புகாருக்கு புகைப்பட அல்லது வீடியோ ஆதாரம் எதுவும் இணைக்கப்படவில்லை.",
    status_history_timeline: "புகார் நிலை வரலாற்று காலவரிசை",
    back_to_dashboard: "முகப்பிற்குச் செல்லவும்",
    copy_id: "புகார் எண்ணை நகலெடுக்க",

    // Auth Pages
    citizen_login: "குடிமக்கள் உள்நுழைவு",
    citizen_login_sub: "புகார்களைப் பதிவு செய்யவும் கண்காணிக்கவும் உள்நுழையவும்.",
    citizen_register: "குடிமக்கள் பதிவு",
    citizen_register_sub: "புகார்களைப் பதிவு செய்ய உங்கள் குடிமக்கள் கணக்கை உருவாக்கவும்.",
    email_address: "மின்னஞ்சல் முகவரி",
    password: "கடவுச்சொல்",
    confirm_password: "கடவுச்சொல்லை உறுதிப்படுத்தவும்",
    full_name: "முழுப் பெயர்",
    preferred_comm_lang: "தொடர்புக்கான விருப்ப மொழி",
    dont_have_account: "இன்னும் கணக்கு இல்லையா?",
    already_have_account: "ஏற்கனவே கணக்கு உள்ளதா?",
    register_here: "இங்கே பதிவு செய்க",
    login_here: "இங்கே உள்நுழைக",
    log_in_btn: "உள்நுழைக",
    register_btn: "குடிமகனாகப் பதிவு செய்க",

    // Wizard Stepper
    wizard_step_1: "ஆதாரம்",
    wizard_step_2: "இடம்",
    wizard_step_3: "விளக்கம்",
    wizard_step_4: "வகை",
    wizard_step_5: "சரிபார்த்தல்",

    // Wizard Step 1: Evidence
    wizard_step1_title: "பிரச்சனையை எவ்வாறு தெரிவிக்க விரும்புகிறீர்கள்?",
    wizard_step1_sub: "சிக்கலை அதிகாரிகள் விரைவாகக் கண்டறிய புகைப்படம், வீடியோ அல்லது குரல் ஆதாரத்தைப் பதிவேற்றவும்.",
    take_upload_photo: "புகைப்படம் எடுக்க / பதிவேற்ற",
    upload_video: "வீடியோ பதிவேற்ற",
    record_voice: "குரல் பதிவு / பதிவேற்ற",
    describe_with_text: "எழுத்து மூலம் விவரிக்க",
    proceed_no_media: "கோப்பு இல்லாமல் தொடரவும்",
    continue_to_location: "இடத்தைத் தேர்வு செய்ய தொடரவும்",

    // Wizard Step 2: Location
    wizard_step2_title: "பிரச்சனை எங்கு உள்ளது?",
    wizard_step2_sub: "துல்லியமான இடம் கள ஆய்வாளர்கள் சரியான இடத்தை அடைய உதவுகிறது.",
    use_current_location: "எனது தற்போதைய இருப்பிடத்தைப் பயன்படுத்து",
    gps_click_hint: "உங்கள் சாதனத்தின் GPS மூலம் இருப்பிடத்தைக் கண்டறிய கிளிக் செய்யவும்.",
    or_enter_coords: "— அல்லது ஆயத்தொலைவுகளை கைமுறையாக உள்ளிடவும் (விருப்பத்தேர்வு) —",
    latitude_label: "அட்சரேகை (Latitude)",
    longitude_label: "தீர்க்கரேகை (Longitude)",
    continue_to_description: "விளக்கம் அளிக்க தொடரவும்",

    // Wizard Step 3: Description
    wizard_step3_title: "பிரச்சனை என்ன?",
    wizard_step3_sub: "துறை அதிகாரிகள் அதன் அவசரத்தைப் புரிந்துகொள்ள சிக்கலை விவரிக்கவும்.",
    lang_for_description: "விளக்கத்திற்கான மொழி",
    description_label: "விளக்கம் (ஆதாரம் வழங்கப்பட்டிருந்தால் விருப்பத்தேர்வு)",
    description_placeholder: "எ.கா. சாலையின் சந்திப்பில் பெரிய ஆபத்தான குழி உள்ளது...",
    continue_to_issue: "பிரச்சனை வகையைத் தேர்ந்தெடுக்க தொடரவும்",

    // Wizard Step 4: Issue & AI
    wizard_step4_title: "குடிமைப் பிரச்சனை வகைப்பாடு",
    wizard_step4_sub: "பதிவேற்றப்பட்ட ஆதாரத்திலிருந்து AI கணிப்பு அல்லது நேரடி வகை தேர்வு.",
    ai_status_notice: "தானியங்கி வகை கண்டறிதல் மற்றும் துறை ஒதுக்கீட்டிற்கு புகைப்படத்தைப் பதிவேற்றவும்.",
    citizen_notice_title: "குடிமக்கள் அறிவிப்பு:",
    dev_fallback_label: "குடிமக்கள் அறிவிப்பு:",
    auto_assigned_dept: "தானாக ஒதுக்கப்பட்ட துறை",
    ai_analyzing_evidence: "YOLO நரம்பியல் வலைப்பின்னல் மூலம் படம் ஆராயப்படுகிறது...",
    ai_validating_raster: "படத்தை சரிபார்த்து ஆழ்நிலை கற்றல் மூலம் கணிக்கப்படுகிறது",
    ai_detection: "YOLO AI கண்டறிதல் செயல்பாட்டில் உள்ளது",
    detected_issue: "கண்டறியப்பட்ட பிரச்சனை",
    confidence: "நம்பகத்தன்மை",
    severity: "தீவிரத்தன்மை",
    department: "ஒதுக்கப்பட்ட துறை",
    ai_citizen_review: "குடிமக்கள் ஆய்வு: AI இந்த சிக்கலைத் தேர்ந்தெடுத்துள்ளது. நீங்கள் உறுதிப்படுத்தலாம் அல்லது மாற்றலாம்.",
    ai_multiple_objects: "பல பொருட்கள் கண்டறியப்பட்டன",
    ai_model_not_available: "படம் வெற்றிகரமாக பதிவேற்றப்பட்டது. தொடர சிக்கல் வகையை உறுதிப்படுத்தவும்.",
    no_detection: "குடிமைச் சிக்கல் கண்டறியப்படவில்லை: படத்திலிருந்து போதுமான நம்பகத்தன்மையுடன் சிக்கல் ஏதும் கண்டறியப்படவில்லை. கீழே உள்ள வகையைத் தேர்ந்தெடுக்கவும்.",
    inference_failed: "AI கணிப்புப் பிழை: படத்தை செயலாக்க முடியவில்லை. கீழே கைமுறையாகத் தேர்ந்தெடுக்கலாம்.",
    select_confirm_category: "வகையைத் தேர்ந்தெடுக்கவும் / உறுதிப்படுத்தவும்",
    click_choose_override: "தேர்வு செய்ய அல்லது மாற்ற கிளிக் செய்யவும்",
    continue_to_review: "சரிபார்க்க தொடரவும்",

    // Wizard Step 5: Review & Duplicates
    wizard_step5_title: "புகாரைச் சரிபார்த்துச் சமர்ப்பிக்கவும்",
    wizard_step5_sub: "நகராட்சி அதிகாரிகளிடம் சமர்ப்பிக்கும் முன் புகார் விவரங்களைச் சரிபார்க்கவும்.",
    review_issue_category: "பிரச்சனை வகை:",
    review_assigned_dept: "ஒதுக்கப்பட்ட துறை:",
    review_ai_class: "AI வகைப்பாடு:",
    review_severity_level: "தீவிரத்தன்மை நிலை:",
    review_location: "இடம்:",
    review_description: "விளக்கம்:",
    review_evidence: "ஆதாரக் கோப்பு:",
    routing_dispatch_notice: "உங்கள் புகார் தானாகவே சம்பந்தப்பட்ட நகராட்சி துறைக்கு அனுப்பப்படும்.",
    submit_complaint: "புகாரைச் சமர்ப்பிக்கவும்",
    complaint_submitted: "புகார் வெற்றிகரமாகப் பதிவு செய்யப்பட்டது",

    // Duplicate Warnings
    checking_duplicates: "இதேபோன்ற முந்தைய புகார்கள் சரிபார்க்கப்படுகின்றன...",
    possible_duplicate: "ஏற்கனவே பதிவு செய்யப்பட்ட புகார் கண்டறியப்பட்டது",
    similar_complaint_found: "இதே பகுதியில் இந்த பிரச்சனை குறித்து சமீபத்தில் ஏற்கனவே புகார் பதிவு செய்யப்பட்டுள்ளது.",
    continue_anyway: "இருப்பினும் சமர்ப்பிக்கவும்",
    view_existing_complaint: "ஏற்கனவே உள்ள புகாரைக் காண்க",
    distance: "தூரம்",
    similarity: "ஒற்றுமை",
    duplicate_reason: "காரணம்",

    // Statuses
    submitted: "சமர்ப்பிக்கப்பட்டது",
    in_review: "பரிசீலனையில் உள்ளது",
    assigned: "துறை ஒதுக்கப்பட்டது",
    in_progress: "செயல்பாட்டில் உள்ளது",
    resolved: "தீர்க்கப்பட்டது",
    rejected: "நிராகரிக்கப்பட்டது",
    ai_verified: "AI மூலம் சரிபார்க்கப்பட்டது",
    needs_human_review: "மனித ஆய்வு தேவை",

    // Resolution Verification
    resolution_verification: "தீர்வு சான்றுகள் சரிபார்ப்பு",
    before_evidence: "முந்தைய / அசல் சான்று",
    after_evidence: "பிந்தைய / தீர்வு சான்று",
    verification_status: "சரிபார்ப்பு நிலை",
    verification_score: "சரிபார்ப்பு மதிப்பீடு",
    verification_reason: "பகுப்பாய்வு காரணம்",
    human_review_required: "மனித ஆய்வு தேவைப்படுகிறது",
    run_verification: "சரிபார்ப்பை இயக்கு",
    review_result: "முடிவை ஆய்வு செய்க",
    approve: "தீர்வை ஏற்கவும்",
    reject: "தீர்வை நிராகரிக்கவும்",
    verification_not_available: "சரிபார்ப்பு கிடைக்கவில்லை",
    pending_verification: "சரிபார்ப்பு நிலுவையில் உள்ளது",
    verification_failed: "சரிபார்ப்பு தோல்வியடைந்தது",
    resolution_evidence: "தீர்வு சான்று",
    visual_comparison: "காட்சி சான்றுகள் ஒப்பீடு",

    // Blockchain Integrity
    blockchain: "பிளாக்செயின்",
    blockchain_status: "பிளாக்செயின் நிலை",
    blockchain_confirmed: "பிளாக்செயினில் உறுதிசெய்யப்பட்டது",
    blockchain_pending: "பிளாக்செயின் நிலுவையில் உள்ளது",
    blockchain_failed: "பிளாக்செயின் தோல்வியடைந்தது",
    blockchain_unavailable: "பிளாக்செயின் இணைக்கப்படவில்லை",
    blockchain_not_configured: "பிளாக்செயின் கட்டமைக்கப்படவில்லை",
    integrity_record: "நேர்மைப் பதிவு",
    transaction_hash: "பரிவர்த்தனை குறியீடு (Tx Hash)",
    block_number: "பிளாக் எண்",
    verify_integrity: "நேர்மையைச் சரிபார்க்கவும்",
    retry_blockchain: "மீண்டும் முயற்சிக்கவும்",

    // Chatbot & Knowledge Base (Steps 11 + 12)
    civic_assistant: "சிவிக் AI உதவியாளர்",
    knowledge_base: "அறிவுத் தளம்",
    civic_conversations: "குடிமக்கள் உரையாடல்கள்",
    new_chat: "+ புதிய உரையாடல்",
    sources: "அதிகாரப்பூர்வ ஆதாரங்கள்",
    ask_question: "ஒரு குடிமை கேள்வியைக் கேளுங்கள்...",
    rebuild_index: "குறியீட்டை மீண்டும் உருவாக்கு",
    document_uploaded: "ஆவணம் வெற்றிகரமாக பதிவேற்றப்பட்டது",
    retrieval_success: "அடிப்படைத் தகவல் மீட்டெடுப்பு செயலில் உள்ளது",
    no_relevant_context: "நகராட்சி வழிகாட்டுதல்களில் நேரடி பொருத்தம் இல்லை",

    // Severities
    low: "குறைந்த",
    medium: "நடுத்தர",
    high: "அதிக",
    critical: "அவசர",

    // Step 13 & 14 Citizen Dashboard & Tracking
    welcome_prefix: "வரவேற்கிறோம்",
    citizen_welcome_desc: "நகரப் பிரச்சனைகளை எளிதாகப் புகாரளிக்கவும். எங்கள் தளம் சிக்கலைக் கண்டறிந்து, தீவிரம் தீர்மானித்து உரிய துறைக்கு அனுப்புகிறது.",
    action_report_title: "பிரச்சினையைப் புகாரளிக்கவும்",
    action_report_desc: "புகார் அளிக்க புகைப்படம், வீடியோ, குரல் அல்லது உரையைப் பதிவேற்றவும்.",
    action_complaints_title: "எனது புகார்கள்",
    action_complaints_desc: "உங்கள் கணக்கிலிருந்து சமர்ப்பிக்கப்பட்ட அனைத்து குறைகளையும் பார்க்கவும்.",
    action_track_title: "புகாரைக் கண்காணிக்கவும்",
    action_track_desc: "புகார் தீர்வு நிலை, காலவரிசை மற்றும் ஒதுக்கப்பட்ட துறையைக் கண்காணிக்கவும்.",
    action_assistant_title: "நாடளாவிய உதவியாளர்",
    action_assistant_desc: "எங்கள் ஏஐ உதவியாளரிடம் நகராட்சி நடைமுறைகள் குறித்த கேள்விகளைக் கேட்கவும்.",
    get_started: "தொடங்கு →",
    view_all: "புகார்களைப் பார்க்கவும் ↓",
    track_now: "நிலையைக் கண்காணிக்கவும் →",
    ask_assistant: "உதவியாளரிடம் கேட்கவும் →",
    complaint_summary_heading: "புகார் சுருக்கம்",
    stat_total_complaints: "மொத்தப் புகார்கள்",
    stat_total_sub: "பதிவுசெய்யப்பட்ட அனைத்து புகார்கள்",
    stat_submitted: "சமர்ப்பிக்கப்பட்டது",
    stat_submitted_sub: "சரிபார்ப்புக்காகக் காத்திருக்கிறது",
    stat_in_progress: "செயலில் உள்ளது",
    stat_inprogress_sub: "களப் பழுதுபார்ப்பு செயலில் உள்ளது",
    stat_resolved: "தீர்க்கப்பட்டது",
    stat_resolved_sub: "சரிபார்க்கப்பட்டு மூடப்பட்டது",
    recent_complaints_heading: "எனது சமீபத்திய புகார்கள்",
    recent_complaints_sub: "உங்கள் புகார்களின் நிகழ்நேர நிலை விவரங்கள்.",
    no_complaints_title: "இன்னும் புகார்கள் எதுவும் சமர்ப்பிக்கப்படவில்லை.",
    report_first_problem: "உங்கள் முதல் புகாரைப் பதிவு செய்யவும்",
    track_grievance_title: "உங்கள் புகாரைக் கண்காணிக்கவும்",
    track_grievance_sub: "தீர்வு முன்னேற்றத்தைக் கண்காணிக்க உங்கள் அதிகாரப்பூர்வ புகார் எண்ணை (CG-YYYY-XXXXXX) உள்ளிடவும்.",
    workflow_progress: "தீர்வு பணிப்பாய்வு முன்னேற்றம்",
    profile_title: "குடிமக்கள் சுயவிவரம்",
    profile_sub: "தனிப்பட்ட விவரங்கள் மற்றும் அறிவிப்பு மொழி விருப்பங்களை நிர்வகிக்கவும்.",
    full_name: "முழு பெயர்",
    preferred_language: "விருப்ப மொழி",
    portal_role: "கணக்கு பங்கு",
    member_since: "உறுப்பினரான தேதி",
    save_changes: "மாற்றங்களைச் சேமிக்கவும்",
    resolution_report_heading: "அதிகாரப்பூர்வ புகார் தீர்வு அறிக்கை",
    resolution_report_sub: "இந்தக் குறை நகராட்சித் துறையால் அதிகாரப்பூர்வமாகத் தீர்க்கப்பட்டு சரிபார்க்கப்பட்டது.",
    resolution_remarks: "அதிகாரியின் தீர்வு குறிப்புகள்",

    // Errors
    invalid_file: "செல்லாத அல்லது சிதைந்த கோப்பு பதிவேற்றப்பட்டது.",
    invalid_location: "தவறான புவியியல் ஆயத்தொலைவுகள் வழங்கப்பட்டுள்ளன.",
    unauthorized: "இந்தச் செயலைச் செய்ய நீங்கள் உள்நுழைய வேண்டும்.",
    network_error: "நெட்வொர்க் இணைப்பு தோல்வியடைந்தது. இணைப்பைச் சரிபார்க்கவும்.",
    server_error: "சேவையகத்தில் எதிர்பாராத பிழை ஏற்பட்டது.",
    required_field: "இப்புலம் அவசியமானது.",
  },

  // ==========================================
  // HINDI (hi)
  // ==========================================
  hi: {
    // Brand & Navigation
    app_name: "एआई सिविक गार्जियन",
    brand_name: "एआई सिविक गार्जियन",
    brand_tagline: "नागरिक शिकायत निवारण प्रणाली",
    welcome: "स्वागत है",
    home: "होम",
    dashboard: "मेरा डैशबोर्ड",
    login: "लॉग इन",
    register: "पंजीकरण",
    logout: "लॉग आउट",
    profile: "प्रोफ़ाइल",
    complaint: "शिकायत",
    complaint_id: "शिकायत संख्या",
    issue_type: "समस्या की श्रेणी",
    description: "विवरण",
    location: "स्थान",
    upload_image: "फोटो खींचें / अपलोड करें",
    review: "समीक्षा करें",
    track_complaint: "शिकायत ट्रैक करें",
    ai_processing: "YOLO न्यूरल नेटवर्क द्वारा साक्ष्य का विश्लेषण किया जा रहा है...",
    review_ai_result: "नागरिक समीक्षा: एआई ने यह श्रेणी चुनी है। आप इसे नीचे बदल या पुष्टि कर सकते हैं।",
    department_assigned: "विभाग आवंटित",
    report_problem: "समस्या दर्ज करें",
    select_language: "भाषा चुनें",

    // General Controls
    submit: "जमा करें",
    cancel: "रद्द करें",
    back: "पीछे",
    next: "आगे",
    previous: "पिछला",
    save: "सहेजें",
    close: "बंद करें",
    confirm: "पुष्टि करें",
    continue: "जारी रखें",
    loading: "लोड हो रहा है...",
    error: "त्रुटि",
    success: "सफलता",
    refresh: "रीफ्रेश करें",
    view_details: "विवरण देखें",
    remove: "हटाएं",

    // Landing / Hero
    hero_title: "नागरिक समस्याओं को आसानी से दर्ज करें",
    hero_sub: "सड़क, कचरा, पानी या बिजली जैसी नागरिक समस्याओं को सीधे नगर निगम अधिकारियों तक पहुँचाएँ।",
    how_it_works: "एआई सिविक गार्जियन कैसे काम करता है",
    step1_hero: "फोटो अपलोड करें",
    step1_hero_desc: "समस्या का फोटो या वीडियो साक्ष्य संलग्न करें।",
    step2_hero: "स्थान जोड़ें",
    step2_hero_desc: "GPS लोकेशन या पता दर्ज करें।",
    step3_hero: "विवरण लिखें",
    step3_hero_desc: "अपनी पसंदीदा भाषा में समस्या का विवरण दें।",
    step4_hero: "प्रगति ट्रैक करें",
    step4_hero_desc: "शिकायत समाधान की स्थिति ऑनलाइन देखें।",

    // Dashboard
    welcome_citizen: "स्वागत है",
    my_complaints: "मेरी शिकायतें",
    no_complaints: "आपने अभी तक कोई शिकायत दर्ज नहीं की है।",
    no_complaints_sub: "अपनी पहली शिकायत दर्ज करने के लिए 'समस्या दर्ज करें' पर क्लिक करें।",
    manage_monitor_sub: "अपनी दर्ज की गई सभी नागरिक शिकायतों की स्थिति यहाँ देखें।",
    routing_in_progress: "विभाग आवंटन प्रक्रियाधीन है",

    // Complaint Tracking / Detail
    grievance_tracking_num: "शिकायत ट्रैकिंग संख्या",
    grievance_description: "शिकायत का विवरण",
    assigned_department: "आवंटित विभाग",
    gps_coordinates: "भौगोलिक निर्देशांक",
    logged_at: "दर्ज करने का समय",
    attached_evidence: "संलग्न साक्ष्य",
    no_evidence_notice: "इस शिकायत के साथ कोई फोटो या वीडियो साक्ष्य संलग्न नहीं है।",
    status_history_timeline: "शिकायत स्थिति समयरेखा",
    back_to_dashboard: "डैशबोर्ड पर वापस जाएं",
    copy_id: "शिकायत संख्या कॉपी करें",

    // Auth Pages
    citizen_login: "नागरिक लॉगिन",
    citizen_login_sub: "शिकायत दर्ज करने और ट्रैक करने के लिए अपने पोर्टल में लॉगिन करें।",
    citizen_register: "नागरिक पंजीकरण",
    citizen_register_sub: "शिकायत दर्ज करने के लिए अपना नागरिक खाता बनाएं।",
    email_address: "ईमेल पता",
    password: "पासवर्ड",
    confirm_password: "पासवर्ड की पुष्टि करें",
    full_name: "पूरा नाम",
    preferred_comm_lang: "संचार के लिए पसंदीदा भाषा",
    dont_have_account: "क्या आपका खाता नहीं है?",
    already_have_account: "क्या आपके पास पहले से खाता है?",
    register_here: "यहाँ पंजीकरण करें",
    login_here: "यहाँ लॉगिन करें",
    log_in_btn: "लॉग इन",
    register_btn: "नागरिक के रूप में पंजीकरण करें",

    // Wizard Stepper
    wizard_step_1: "साक्ष्य",
    wizard_step_2: "स्थान",
    wizard_step_3: "विवरण",
    wizard_step_4: "समस्या",
    wizard_step_5: "समीक्षा",

    // Wizard Step 1: Evidence
    wizard_step1_title: "आप समस्या की रिपोर्ट कैसे करना चाहते हैं?",
    wizard_step1_sub: "अधिकारियों को समस्या की तुरंत पहचान करने में मदद के लिए फोटो, वीडियो या आवाज साक्ष्य अपलोड करें।",
    take_upload_photo: "फोटो खींचें / अपलोड करें",
    upload_video: "वीडियो अपलोड करें",
    record_voice: "आवाज रिकॉर्ड / अपलोड करें",
    describe_with_text: "केवल लिखकर विवरण दें",
    proceed_no_media: "बिना मीडिया फ़ाइल के आगे बढ़ें",
    continue_to_location: "स्थान जोड़ने के लिए आगे बढ़ें",

    // Wizard Step 2: Location
    wizard_step2_title: "समस्या कहाँ है?",
    wizard_step2_sub: "सटीक स्थान होने पर नगर निगम दल तुरंत सही जगह पहुँच सकता है।",
    use_current_location: "मेरे वर्तमान स्थान का उपयोग करें",
    gps_click_hint: "अपने डिवाइस के GPS द्वारा स्थान का पता लगाने के लिए क्लिक करें।",
    or_enter_coords: "— या निर्देशांक मैन्युअल रूप से दर्ज करें (वैकल्पिक) —",
    latitude_label: "अक्षांश (Latitude)",
    longitude_label: "देशांतर (Longitude)",
    continue_to_description: "विवरण लिखने के लिए आगे बढ़ें",

    // Wizard Step 3: Description
    wizard_step3_title: "समस्या क्या है?",
    wizard_step3_sub: "समस्या का विवरण दें ताकि संबंधित विभाग इसकी तात्कालिकता समझ सके।",
    lang_for_description: "विवरण के लिए भाषा",
    description_label: "विवरण (यदि साक्ष्य संलग्न है तो वैकल्पिक)",
    description_placeholder: "उदा. सड़क के चौराहे के पास बहुत बड़ा गड्ढा है जिससे दुर्घटना का खतरा है...",
    continue_to_issue: "समस्या प्रकार चुनने के लिए आगे बढ़ें",

    // Wizard Step 4: Issue & AI
    wizard_step4_title: "नागरिक समस्या वर्गीकरण",
    wizard_step4_sub: "अपलोड किए गए साक्ष्य से एआई पहचान अथवा मैन्युअल श्रेणी चयन।",
    ai_status_notice: "स्वचालित श्रेणी पहचान और विभाग आवंटन के लिए एक फोटो अपलोड करें।",
    citizen_notice_title: "नागरिक सूचना:",
    dev_fallback_label: "नागरिक सूचना:",
    auto_assigned_dept: "स्वचालित रूप से आवंटित विभाग",
    ai_analyzing_evidence: "YOLO न्यूरल नेटवर्क द्वारा साक्ष्य का विश्लेषण किया जा रहा है...",
    ai_validating_raster: "छवि की पुष्टि और डीप लर्निंग निष्कर्ष निकाला जा रहा है",
    ai_detection: "YOLO एआई पहचान सक्रिय",
    detected_issue: "पहचानी गई समस्या",
    confidence: "सटीकता",
    severity: "गंभीरता",
    department: "आवंटित विभाग",
    ai_citizen_review: "नागरिक समीक्षा: एआई ने यह श्रेणी चुनी है। आप इसे नीचे बदल या पुष्टि कर सकते हैं।",
    ai_multiple_objects: "कई वस्तुएं पहचानी गईं",
    ai_model_not_available: "छवि सफलतापूर्वक अपलोड हो गई। जारी रखने के लिए कृपया समस्या श्रेणी की पुष्टि करें।",
    no_detection: "कोई नागरिक समस्या नहीं मिली: एआई मॉडल ने छवि का विश्लेषण किया लेकिन कोई नागरिक समस्या पर्याप्त विश्वास से नहीं मिली। नीचे से श्रेणी चुनें।",
    inference_failed: "एआई निष्कर्ष त्रुटि: छवि का विश्लेषण नहीं हो सका। आप नीचे मैन्युअल रूप से श्रेणी चुन सकते हैं।",
    select_confirm_category: "श्रेणी चुनें / पुष्टि करें",
    click_choose_override: "चुनने या बदलने के लिए क्लिक करें",
    continue_to_review: "समीक्षा के लिए आगे बढ़ें",

    // Wizard Step 5: Review & Duplicates
    wizard_step5_title: "शिकायत की समीक्षा करें और जमा करें",
    wizard_step5_sub: "नगर निगम को भेजने से पहले अपनी शिकायत के विवरण की पुष्टि करें।",
    review_issue_category: "समस्या की श्रेणी:",
    review_assigned_dept: "आवंटित विभाग:",
    review_ai_class: "एआई वर्गीकरण:",
    review_severity_level: "गंभीरता का स्तर:",
    review_location: "स्थान:",
    review_description: "विवरण:",
    review_evidence: "साक्ष्य फ़ाइल:",
    routing_dispatch_notice: "आपकी शिकायत स्वतः संबंधित नगर निगम विभाग को भेज दी जाएगी।",
    submit_complaint: "शिकायत दर्ज करें",
    complaint_submitted: "शिकायत सफलतापूर्वक दर्ज की गई",

    // Duplicate Warnings
    checking_duplicates: "समान पूर्व शिकायतों की जाँच की जा रही है...",
    possible_duplicate: "संभावित समान शिकायत पाई गई",
    similar_complaint_found: "इस क्षेत्र में हाल ही में इस समस्या से संबंधित शिकायत दर्ज की जा चुकी है।",
    continue_anyway: "फिर भी शिकायत दर्ज करें",
    view_existing_complaint: "मौजूदा शिकायत देखें",
    distance: "दूरी",
    similarity: "समानता",
    duplicate_reason: "कारण",

    // Statuses
    submitted: "जमा किया गया",
    in_review: "समीक्षाधीन",
    assigned: "विभाग आवंटित",
    in_progress: "प्रगति पर है",
    resolved: "समाधान हो गया",
    rejected: "अस्वीकृत",
    ai_verified: "एआई द्वारा सत्यापित",
    needs_human_review: "मानव समीक्षा की आवश्यकता",

    // Resolution Verification
    resolution_verification: "समाधान साक्ष्य सत्यापन",
    before_evidence: "पहले का / मूल साक्ष्य",
    after_evidence: "बाद का / समाधान साक्ष्य",
    verification_status: "सत्यापन स्थिति",
    verification_score: "सत्यापन स्कोर",
    verification_reason: "विश्लेषण कारण",
    human_review_required: "मानव समीक्षा आवश्यक है",
    run_verification: "सत्यापन चलाएं",
    review_result: "परिणाम की समीक्षा करें",
    approve: "समाधान स्वीकृत करें",
    reject: "समाधान अस्वीकृत करें",
    verification_not_available: "सत्यापन उपलब्ध नहीं है",
    pending_verification: "सत्यापन लंबित",
    verification_failed: "सत्यापन विफल रहा",
    resolution_evidence: "समाधान साक्ष्य",
    visual_comparison: "दृश्य साक्ष्य तुलना",

    // Blockchain Integrity
    blockchain: "ब्लॉकचेन",
    blockchain_status: "ब्लॉकचेन स्थिति",
    blockchain_confirmed: "ब्लॉकचेन द्वारा पुष्टीकृत",
    blockchain_pending: "ब्लॉकचेन लंबित",
    blockchain_failed: "ब्लॉकचेन विफल",
    blockchain_unavailable: "ब्लॉकचेन अनुपलब्ध",
    blockchain_not_configured: "ब्लॉकचेन कॉन्फ़िगर नहीं है",
    integrity_record: "अखंडता रिकॉर्ड",
    transaction_hash: "ट्रांज़ैक्शन हैश (Tx Hash)",
    block_number: "ब्लॉक संख्या",
    verify_integrity: "अखंडता सत्यापित करें",
    retry_blockchain: "पुनः प्रयास करें",

    // Chatbot & Knowledge Base (Steps 11 + 12)
    civic_assistant: "नागरिक एआई सहायक",
    knowledge_base: "ज्ञानकोश",
    civic_conversations: "नागरिक संवाद",
    new_chat: "+ नया संवाद",
    sources: "आधिकारिक स्रोत",
    ask_question: "एक नागरिक प्रश्न पूछें...",
    rebuild_index: "इंडेक्स पुनः बनाएं",
    document_uploaded: "दस्तावेज़ सफलतापूर्वक अपलोड किया गया",
    retrieval_success: "पुष्टीकृत जानकारी पुनर्प्राप्ति सक्रिय",
    no_relevant_context: "नगरपालिका दिशानिर्देशों में कोई सीधा मेल नहीं",

    // Severities
    low: "कम",
    medium: "मध्यम",
    high: "उच्च",
    critical: "गंभीर",

    // Step 13 & 14 Citizen Dashboard & Tracking
    welcome_prefix: "स्वागत है",
    citizen_welcome_desc: "नागरिक समस्याओं को आसानी से दर्ज करें। हमारी प्रणाली समस्या की पहचान कर उचित विभाग को आवंटित करती है।",
    action_report_title: "समस्या दर्ज करें",
    action_report_desc: "नई शिकायत दर्ज करने के लिए फोटो, वीडियो, आवाज या टेक्स्ट अपलोड करें।",
    action_complaints_title: "मेरी शिकायतें",
    action_complaints_desc: "अपने खाते द्वारा दर्ज की गई सभी शिकायतें देखें।",
    action_track_title: "शिकायत ट्रैक करें",
    action_track_desc: "शिकायत समाधान स्थिति, समयसीमा और आवंटित विभाग ट्रैक करें।",
    action_assistant_title: "नागरिक सहायक",
    action_assistant_desc: "सरकारी प्रक्रियाओं और नागरिक सेवाओं के बारे में प्रश्न पूछें।",
    get_started: "शुरू करें →",
    view_all: "शिकायतें देखें ↓",
    track_now: "स्थिति ट्रैक करें →",
    ask_assistant: "सहायक से पूछें →",
    complaint_summary_heading: "शिकायत सारांश",
    stat_total_complaints: "कुल शिकायतें",
    stat_total_sub: "सभी दर्ज शिकायतें",
    stat_submitted: "जमा किया गया",
    stat_submitted_sub: "सत्यापन की प्रतीक्षा में",
    stat_in_progress: "प्रगति पर है",
    stat_inprogress_sub: "सक्रिय क्षेत्रीय मरम्मत जारी",
    stat_resolved: "समाधान हो गया",
    stat_resolved_sub: "सत्यापित और बंद",
    recent_complaints_heading: "मेरी हाल की शिकायतें",
    recent_complaints_sub: "आपकी शिकायतों की वास्तविक समय स्थिति।",
    no_complaints_title: "अभी तक कोई शिकायत जमा नहीं की गई है।",
    report_first_problem: "अपनी पहली समस्या दर्ज करें",
    track_grievance_title: "अपनी नागरिक शिकायत ट्रैक करें",
    track_grievance_sub: "समाधान की प्रगति देखने के लिए अपनी शिकायत संख्या (CG-YYYY-XXXXXX) दर्ज करें।",
    workflow_progress: "समाधान कार्यप्रवाह प्रगति",
    profile_title: "नागरिक प्रोफ़ाइल",
    profile_sub: "अपने विवरण और पसंदीदा भाषा प्राथमिकताएं प्रबंधित करें।",
    full_name: "पूरा नाम",
    preferred_language: "पसंदीदा भाषा",
    portal_role: "खाता भूमिका",
    member_since: "सदस्यता तिथि",
    save_changes: "परिवर्तन सहेजें",
    resolution_report_heading: "आधिकारिक शिकायत समाधान रिपोर्ट",
    resolution_report_sub: "यह नागरिक शिकायत नगर निगम विभाग द्वारा सत्यापित और हल की जा चुकी है।",
    resolution_remarks: "अधिकारी समाधान टिप्पणियां",

    // Errors
    invalid_file: "अमान्य या दूषित फ़ाइल अपलोड की गई।",
    invalid_location: "अमान्य भौगोलिक निर्देशांक प्रदान किए गए।",
    unauthorized: "इस क्रिया को करने के लिए आपको लॉग इन करना होगा।",
    network_error: "नेटवर्क संचार विफलता। कृपया अपना इंटरनेट जांचें।",
    server_error: "सर्वर में आंतरिक त्रुटि हुई।",
    required_field: "यह फ़ील्ड आवश्यक है।",
  },
};

// 12 Canonical Issues Dictionary
const ISSUE_TRANSLATIONS = {
  garbage_overflow: {
    en: "Garbage Overflow",
    ta: "குப்பைகள் வழிதல்",
    hi: "कचरा ओवरफ्लो",
  },
  illegal_dumping: {
    en: "Illegal Dumping",
    ta: "சட்டவிரோத குப்பைக் கொட்டுதல்",
    hi: "अवैध कचरा डंपिंग",
  },
  pothole: {
    en: "Pothole",
    ta: "சாலைக் குழி",
    hi: "गड्ढा",
  },
  damaged_road: {
    en: "Damaged Road",
    ta: "சேதமடைந்த சாலை",
    hi: "क्षतिग्रस्त सड़क",
  },
  water_leakage: {
    en: "Water Leakage",
    ta: "குடிநீர் கசிவு",
    hi: "पानी का रिसाव",
  },
  sewage_overflow: {
    en: "Sewage Overflow",
    ta: "கழிவுநீர் வழிதல்",
    hi: "सीवेज ओवरफ्लो",
  },
  broken_street_light: {
    en: "Broken Street Light",
    ta: "பழுதடைந்த தெருவிளக்கு",
    hi: "टूटी स्ट्रीट लाइट",
  },
  drainage_problem: {
    en: "Drainage Problem",
    ta: "வடிகால் பிரச்சனை",
    hi: "जल निकासी समस्या",
  },
  traffic_issue: {
    en: "Traffic Issue",
    ta: "போக்குவரத்து நெரிசல்",
    hi: "यातायात समस्या",
  },
  building_damage: {
    en: "Building Damage",
    ta: "கட்டட சேதம்",
    hi: "इमारत क्षति",
  },
  park_damage: {
    en: "Park / Public Space Damage",
    ta: "பூங்கா / பொது இடம் சேதம்",
    hi: "पार्क / सार्वजनिक स्थान क्षति",
  },
  environmental_pollution: {
    en: "Environmental Pollution",
    ta: "சுற்றுச்சூழல் மாசுபாடு",
    hi: "पर्यावरण प्रदूषण",
  },
};

// Municipal Departments Dictionary
const DEPARTMENT_TRANSLATIONS = {
  "Roads & Highways": {
    en: "Roads & Highways",
    ta: "சாலைகள் மற்றும் நெடுஞ்சாலைகள்",
    hi: "सड़क और राजमार्ग",
  },
  "Solid Waste Management": {
    en: "Solid Waste Management",
    ta: "திடக்கழிவு மேலாண்மை",
    hi: "ठोस अपशिष्ट प्रबंधन",
  },
  "Water Supply & Sewerage": {
    en: "Water Supply & Sewerage",
    ta: "குடிநீர் வழங்கல் மற்றும் கழிவுநீரகற்று வாரியம்",
    hi: "जल आपूर्ति और सीवरेज",
  },
  "Electricity & Street Lighting": {
    en: "Electricity & Street Lighting",
    ta: "மின்சாரம் மற்றும் தெருவிளக்குகள்",
    hi: "बिजली और स्ट्रीट लाइटिंग",
  },
  "Drainage & Flood Management": {
    en: "Drainage & Flood Management",
    ta: "வடிகால் மற்றும் வெள்ள மேலாண்மை",
    hi: "जल निकासी और बाढ़ प्रबंधन",
  },
  "Traffic & Transportation": {
    en: "Traffic & Transportation",
    ta: "போக்குவரத்து மற்றும் இடப்பெயர்வு",
    hi: "यातायात और परिवहन",
  },
  "Building & Construction": {
    en: "Building & Construction",
    ta: "கட்டடங்கள் மற்றும் கட்டுமானம்",
    hi: "भवन और निर्माण",
  },
  "Parks & Public Spaces": {
    en: "Parks & Public Spaces",
    ta: "பூங்காக்கள் மற்றும் பொது இடங்கள்",
    hi: "पार्क और सार्वजनिक स्थान",
  },
  "Environmental Protection": {
    en: "Environmental Protection",
    ta: "சுற்றுச்சூழல் பாதுகாப்பு",
    hi: "पर्यावरण संरक्षण",
  },
  "Public Health & Sanitation": {
    en: "Public Health & Sanitation",
    ta: "பொது சுகாதாரம் மற்றும் துப்புரவு",
    hi: "सार्वजनिक स्वास्थ्य और स्वच्छता",
  },
  "Urban Planning & Municipal Services": {
    en: "Urban Planning & Municipal Services",
    ta: "நகர திட்டமிடல் மற்றும் நகராட்சி சேவைகள்",
    hi: "नगर नियोजन और नगरपालिका सेवाएं",
  },
  "Public Safety": {
    en: "Public Safety",
    ta: "பொதுப் பாதுகாப்பு",
    hi: "सार्वजनिक सुरक्षा",
  },
};

// Statuses Dictionary
const STATUS_TRANSLATIONS = {
  SUBMITTED: {
    en: "Submitted",
    ta: "சமர்ப்பிக்கப்பட்டது",
    hi: "जमा किया गया",
  },
  IN_REVIEW: {
    en: "In Review",
    ta: "பரிசீலனையில் உள்ளது",
    hi: "समीक्षाधीन",
  },
  ASSIGNED: {
    en: "Department Assigned",
    ta: "துறை ஒதுக்கப்பட்டது",
    hi: "विभाग आवंटित",
  },
  DEPARTMENT_ASSIGNED: {
    en: "Department Assigned",
    ta: "துறை ஒதுக்கப்பட்டது",
    hi: "विभाग आवंटित",
  },
  IN_PROGRESS: {
    en: "In Progress",
    ta: "செயல்பாட்டில் உள்ளது",
    hi: "प्रगति पर है",
  },
  RESOLVED: {
    en: "Resolved",
    ta: "தீர்க்கப்பட்டது",
    hi: "समाधान हो गया",
  },
  REJECTED: {
    en: "Rejected",
    ta: "நிராகரிக்கப்பட்டது",
    hi: "अस्वीकृत",
  },
  AI_VERIFIED: {
    en: "AI Verified",
    ta: "AI மூலம் சரிபார்க்கப்பட்டது",
    hi: "एआई द्वारा सत्यापित",
  },
  VERIFIED: {
    en: "Verified",
    ta: "சரிபார்க்கப்பட்டது",
    hi: "सत्यापित",
  },
  NEEDS_HUMAN_REVIEW: {
    en: "Needs Human Review",
    ta: "மனித ஆய்வு தேவை",
    hi: "मानव समीक्षा की आवश्यकता",
  },
};

// Severities Dictionary
const SEVERITY_TRANSLATIONS = {
  LOW: {
    en: "Low",
    ta: "குறைந்த",
    hi: "कम",
  },
  MEDIUM: {
    en: "Medium",
    ta: "நடுத்தர",
    hi: "मध्यम",
  },
  HIGH: {
    en: "High",
    ta: "அதிக",
    hi: "उच्च",
  },
  CRITICAL: {
    en: "Critical",
    ta: "அவசர",
    hi: "गंभीर",
  },
};

/**
 * Get active user language from localStorage or browser language
 */
function getSelectedLanguage() {
  const stored = localStorage.getItem("preferred_lang");
  if (stored && I18N_DATA[stored]) {
    return stored;
  }
  // Try browser language
  const browserLang = (navigator.language || navigator.userLanguage || "en").substring(0, 2).toLowerCase();
  if (I18N_DATA[browserLang]) {
    return browserLang;
  }
  return "en";
}

/**
 * Set and apply the active language dynamically across the page
 */
function setLanguage(lang) {
  const target = I18N_DATA[lang] ? lang : "en";
  localStorage.setItem("preferred_lang", target);
  applyLanguage(target);
  document.dispatchEvent(new CustomEvent("i18n:changed", { detail: { lang: target } }));
}

/**
 * Lookup translated string with fallback hierarchy:
 * 1. Requested language dictionary
 * 2. English baseline dictionary
 * 3. Safe key fallback
 */
function t(key, lang = null) {
  const currentLang = lang || getSelectedLanguage();
  const dict = I18N_DATA[currentLang] || I18N_DATA["en"];
  if (dict && dict[key] !== undefined) {
    return dict[key];
  }
  const enDict = I18N_DATA["en"];
  if (enDict && enDict[key] !== undefined) {
    return enDict[key];
  }
  if (typeof console !== "undefined" && console.warn) {
    console.warn(`[i18n] Missing translation key: "${key}" for lang: "${currentLang}"`);
  }
  return key;
}

/**
 * Translate 12 canonical civic issues
 */
function tIssue(issueKey, lang = null) {
  const currentLang = lang || getSelectedLanguage();
  const canon = (issueKey || "").trim().toLowerCase();
  const entry = ISSUE_TRANSLATIONS[canon];
  if (entry) {
    return entry[currentLang] || entry["en"] || issueKey;
  }
  return issueKey;
}

/**
 * Translate municipal department names
 */
function tDepartment(deptName, lang = null) {
  const currentLang = lang || getSelectedLanguage();
  const clean = (deptName || "").trim();
  const entry = DEPARTMENT_TRANSLATIONS[clean];
  if (entry) {
    return entry[currentLang] || entry["en"] || deptName;
  }
  return deptName;
}

/**
 * Translate complaint status enums
 */
function tStatus(status, lang = null) {
  const currentLang = lang || getSelectedLanguage();
  const clean = (status || "").trim().toUpperCase();
  const entry = STATUS_TRANSLATIONS[clean];
  if (entry) {
    return entry[currentLang] || entry["en"] || status;
  }
  return status;
}

/**
 * Translate severity level
 */
function tSeverity(severity, lang = null) {
  const currentLang = lang || getSelectedLanguage();
  const clean = (severity || "").trim().toUpperCase();
  const entry = SEVERITY_TRANSLATIONS[clean];
  if (entry) {
    return entry[currentLang] || entry["en"] || severity;
  }
  return severity;
}

/**
 * Apply translated strings dynamically to all DOM elements with i18n markers
 */
function applyLanguage(lang) {
  const currentLang = lang || getSelectedLanguage();
  const langData = I18N_DATA[currentLang] || I18N_DATA["en"];

  // Update HTML lang attribute
  if (document.documentElement) {
    document.documentElement.lang = currentLang;
  }

  // Update textContent for [data-i18n]
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (langData[key] !== undefined) {
      el.textContent = langData[key];
    } else if (I18N_DATA["en"][key] !== undefined) {
      el.textContent = I18N_DATA["en"][key];
    }
  });

  // Update placeholder for [data-i18n-placeholder]
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (langData[key] !== undefined) {
      el.placeholder = langData[key];
    } else if (I18N_DATA["en"][key] !== undefined) {
      el.placeholder = I18N_DATA["en"][key];
    }
  });

  // Update title for [data-i18n-title]
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    const key = el.getAttribute("data-i18n-title");
    if (langData[key] !== undefined) {
      el.title = langData[key];
    } else if (I18N_DATA["en"][key] !== undefined) {
      el.title = I18N_DATA["en"][key];
    }
  });

  // Update aria-label for [data-i18n-aria-label]
  document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
    const key = el.getAttribute("data-i18n-aria-label");
    if (langData[key] !== undefined) {
      el.setAttribute("aria-label", langData[key]);
    } else if (I18N_DATA["en"][key] !== undefined) {
      el.setAttribute("aria-label", I18N_DATA["en"][key]);
    }
  });

  // Update issue labels for [data-i18n-issue]
  document.querySelectorAll("[data-i18n-issue]").forEach((el) => {
    const key = el.getAttribute("data-i18n-issue");
    el.textContent = tIssue(key, currentLang);
  });

  // Update department labels for [data-i18n-dept]
  document.querySelectorAll("[data-i18n-dept]").forEach((el) => {
    const key = el.getAttribute("data-i18n-dept");
    el.textContent = tDepartment(key, currentLang);
  });

  // Update status labels for [data-i18n-status]
  document.querySelectorAll("[data-i18n-status]").forEach((el) => {
    const key = el.getAttribute("data-i18n-status");
    el.textContent = tStatus(key, currentLang);
  });

  // Update severity labels for [data-i18n-severity]
  document.querySelectorAll("[data-i18n-severity]").forEach((el) => {
    const key = el.getAttribute("data-i18n-severity");
    el.textContent = tSeverity(key, currentLang);
  });

  // Synchronize language dropdown selectors
  document.querySelectorAll("#lang-switcher, .lang-select").forEach((sel) => {
    sel.value = currentLang;
  });
}

// Global initialization on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  const currentLang = getSelectedLanguage();
  applyLanguage(currentLang);

  document.querySelectorAll("#lang-switcher, .lang-select").forEach((selector) => {
    selector.value = currentLang;
    selector.addEventListener("change", (e) => {
      setLanguage(e.target.value);
    });
  });
});
