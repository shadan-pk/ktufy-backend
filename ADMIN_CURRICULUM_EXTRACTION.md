# Admin Panel — Curriculum Extraction Integration

## Overview

The curriculum extraction feature has been integrated into the KTUfy admin panel, providing a user-friendly interface to:
- Upload curriculum PDFs
- Automatically extract elective group mappings (PEC1-PEC5)
- Store mappings in the database
- View all stored curriculum mappings

## Admin Panel Navigation

### New Navigation Item
- **Extract Curriculum** — Located in the main sidebar, between "Upload Syllabus" and "Subjects"
- Icon: `book-marked` (Lucide icon)

## Using Curriculum Extraction

### Step 1: Access the Feature
1. Open the admin panel (e.g., `http://localhost:8000/admin-panel`)
2. Click **Extract Curriculum** in the sidebar

### Step 2: Upload Curriculum PDF
1. **File Upload** section:
   - Drag & drop a curriculum PDF, or
   - Click the upload zone to browse and select a PDF
2. **Configuration** section:
   - Select the **Branch** (CSE, ECE, EEE, ME, CE)
   - Select the **Regulation** (2019, 2024, 2028)

### Step 3: Extract Mappings
1. Click **Extract Mappings** button
2. Wait for the extraction process (typically 30-60 seconds depending on PDF size)
3. Monitor the progress with the loading indicator

### Step 4: View Results
- **Extraction Result** card displays:
  - Status (Success/Failure)
  - Number of mappings extracted
  - Number of mappings inserted into database
  - Branch, regulation, and timestamp
- **Stored Mappings** table shows all extracted mappings:
  - Subject Code
  - Subject Name
  - Program Elective (PEC1-PEC5)
  - Semester, Credits
  - Branch, Regulation

## API Endpoints

### Extract Curriculum Mappings
**Endpoint:** `POST /api/v2/admin/extract-curriculum`

**Request:**
```multipart/form-data
- file: <PDF file>
- branch: string (CSE, ECE, EEE, ME, CE)
- regulation: string (2019, 2024, 2028) [default: 2019]
```

**Response:**
```json
{
  "status": "success",
  "message": "Extracted and stored 45 elective mappings",
  "mappings_extracted": 45,
  "mappings_inserted": 45,
  "branch": "CSE",
  "regulation": "2019",
  "timestamp": "2026-05-06T10:30:00"
}
```

### Get Curriculum Mappings
**Endpoint:** `GET /api/v2/admin/curriculum-mappings`

**Query Parameters:**
- `branch` (optional): Filter by branch code
- `regulation` (optional): Filter by regulation year

**Response:**
```json
{
  "status": "success",
  "total": 45,
  "mappings": [
    {
      "subject_code": "CST3E1",
      "subject_name": "Advanced Algorithms",
      "program_elective": "PEC1",
      "semester": 3,
      "credits": 4,
      "branch": "CSE",
      "regulation": "2019"
    }
  ],
  "branch": "CSE",
  "regulation": "2019"
}
```

## UI Components

### File Upload Zone
- Drag & drop support
- Click to browse
- Displays selected filename
- Visual feedback on drag hover

### Configuration Section
- Custom dropdowns for Branch and Regulation
- Styled with Shadcn design tokens
- Disabled until file is selected

### Extraction Result
- Displays extraction status
- Shows statistics (extracted vs inserted)
- Color-coded success/failure indicators
- Auto-hides if no result yet

### Stored Mappings Table
- Real-time display of all mappings in database
- Filter by branch and regulation
- Refresh button to reload data
- Color-coded program_elective badges:
  - PEC1: Blue
  - PEC2: Purple
  - PEC3: Pink
  - PEC4: Orange
  - PEC5: Cyan
  - PCC: Green
  - OEC: Indigo

## Features

✅ **Drag & Drop File Upload** — Intuitive file selection

✅ **Automatic LLM Extraction** — Uses GPT-4o-mini to parse curriculum PDFs

✅ **Database Integration** — Automatic upsert to syllabus_elective_mappings table

✅ **Real-time Results** — Immediate feedback on extraction success/failure

✅ **Mapping Visualization** — Browse all extracted mappings in an easy-to-read table

✅ **Error Handling** — Clear error messages if extraction fails

✅ **Responsive Design** — Works on desktop, tablet, mobile

## File References

### Backend
- **API Endpoints:** [routers/admin_v2.py](routers/admin_v2.py#L328)
- **Models:** [CurriculumExtractionResponse](routers/admin_v2.py#L114)

### Frontend
- **HTML:** [templates/admin.html](templates/admin.html#L695)
- **JavaScript:** [static/js/curriculum.js](static/js/curriculum.js)
- **Admin JS Integration:** [static/js/admin.js](static/js/admin.js#L210)

## Workflow Integration

**Curriculum Extraction Flow:**
```
Upload PDF → Extract with LLM → Validate mappings → Store in DB
              ↓
        Returned to UI
              ↓
        Refresh mappings table
              ↓
        Display results & statistics
```

**Syllabus Processing with Curriculum Context:**
```
Process syllabus PDF → Load curriculum mappings → Pass to LLM
                            ↓
                      LLM uses hints
                            ↓
                      Assigns program_elective
                            ↓
                      Store with category
```

## Troubleshooting

### File Upload Not Working
- Ensure file is a valid PDF
- Check browser console for JavaScript errors
- Verify file size is reasonable (<50MB)

### Extraction Fails
- Check admin panel for error message
- Verify curriculum PDF format is correct
- Ensure OpenAI API is configured
- Check browser console logs

### Mappings Not Appearing
- Refresh the mappings table using the Refresh button
- Check database connection is active
- Verify Supabase configuration

### Performance Issues
- Large PDFs (>100 pages) may take longer to process
- LLM extraction is the bottleneck (~1-2 minutes for large files)
- Consider extracting smaller PDFs in batches

## Future Enhancements

- [ ] Batch extraction for multiple curriculum PDFs
- [ ] Edit/delete individual mappings
- [ ] Export mappings to CSV
- [ ] Conflict detection (mapping vs. extracted subjects)
- [ ] Audit trail for all extraction operations
- [ ] Preview extracted mappings before storing

---

**Last Updated:** Session 3
**Status:** ✅ Integrated into admin panel
**Version:** 1.0
