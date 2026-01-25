# Graider Lesson Planner - Implementation Plan

## Overview

Transform Graider from a grading tool into a full AI teaching assistant with:
- State standards database (starting with Florida)
- AI-generated lesson plans aligned to standards
- Unit planning with day-by-day breakdowns
- Integration with existing assignment builder and grader

---

## New Tab Structure

```
[ 🏠 Home ] [ 📊 Results ] [ 📧 Emails ] [ 📝 Builder ] [ 📚 Planner ] [ ⚙️ Settings ]
                                                            ↑ NEW
```

---

## State Variables to Add

```javascript
// Add after existing state declarations (around line 224)

// Planner State
const [plannerConfig, setPlannerConfig] = React.useState({
    state: 'FL',
    grade: '7',
    subject: 'Civics'
});

const [standards, setStandards] = React.useState([]);
const [selectedStandards, setSelectedStandards] = React.useState([]);
const [lessonPlan, setLessonPlan] = React.useState(null);
const [plannerLoading, setPlannerLoading] = React.useState(false);
const [unitConfig, setUnitConfig] = React.useState({
    title: '',
    duration: 5,  // days
    startDate: ''
});
```

---

## Standards Data Structure

```javascript
// Florida B.E.S.T. Standards - Civics 7th Grade (Example)
const FLORIDA_STANDARDS = {
    "FL": {
        "Civics": {
            "7": [
                {
                    code: "SS.7.CG.1.1",
                    benchmark: "Analyze the influences of ancient Greece, Rome, and the Judeo-Christian tradition on America's founding principles.",
                    topics: ["Ancient Greece", "Roman Republic", "Judeo-Christian values", "Natural rights"]
                },
                {
                    code: "SS.7.CG.1.2",
                    benchmark: "Trace the impact of Enlightenment philosophers on the American Founding Fathers.",
                    topics: ["Locke", "Montesquieu", "Rousseau", "Social contract"]
                },
                {
                    code: "SS.7.CG.1.3",
                    benchmark: "Explain how the ideas expressed in the Declaration of Independence contributed to the American Revolution.",
                    topics: ["Declaration of Independence", "Natural rights", "Consent of governed"]
                },
                {
                    code: "SS.7.CG.2.1",
                    benchmark: "Explain the advantages and disadvantages of the Articles of Confederation.",
                    topics: ["Articles of Confederation", "Weaknesses", "Shays Rebellion"]
                },
                // ... more standards
            ],
            "6": [ /* 6th grade standards */ ],
            "8": [ /* 8th grade standards */ ]
        },
        "US History": {
            "8": [ /* standards */ ]
        },
        "Social Studies": {
            "6": [ /* standards */ ],
            "7": [ /* standards */ ]
        }
    }
};
```

---

## New UI Components

### 1. Planner Tab Header
```javascript
// Location: Inside the tab content area, after Settings tab content

{activeTab === 'planner' && (
    <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, marginBottom: '25px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Icon name="BookOpen" size={28} />Lesson Planner
        </h1>
        
        {/* Configuration Section */}
        {/* Standards Browser */}
        {/* Unit Planner */}
        {/* Generated Lessons */}
    </div>
)}
```

### 2. Configuration Section
```javascript
{/* State/Grade/Subject Selectors */}
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '25px' }}>
    
    {/* State Selector */}
    <div style={{ padding: '20px', background: 'rgba(99,102,241,0.1)', borderRadius: '12px', border: '1px solid rgba(99,102,241,0.2)' }}>
        <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 600, marginBottom: '10px' }}>
            <Icon name="MapPin" size={16} style={{ marginRight: '8px' }} />State
        </label>
        <select value={plannerConfig.state} onChange={e => setPlannerConfig({...plannerConfig, state: e.target.value})}
            style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.3)', color: '#fff', fontSize: '1rem' }}>
            <option value="FL">Florida</option>
            <option value="TX">Texas</option>
            <option value="CA">California</option>
            <option value="NY">New York</option>
            <option value="CC">Common Core</option>
        </select>
    </div>
    
    {/* Grade Selector */}
    <div style={{ padding: '20px', background: 'rgba(99,102,241,0.1)', borderRadius: '12px', border: '1px solid rgba(99,102,241,0.2)' }}>
        <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 600, marginBottom: '10px' }}>
            <Icon name="GraduationCap" size={16} style={{ marginRight: '8px' }} />Grade Level
        </label>
        <select value={plannerConfig.grade} onChange={e => setPlannerConfig({...plannerConfig, grade: e.target.value})}
            style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.3)', color: '#fff', fontSize: '1rem' }}>
            <option value="6">6th Grade</option>
            <option value="7">7th Grade</option>
            <option value="8">8th Grade</option>
            <option value="9">9th Grade</option>
            <option value="10">10th Grade</option>
            <option value="11">11th Grade</option>
            <option value="12">12th Grade</option>
        </select>
    </div>
    
    {/* Subject Selector */}
    <div style={{ padding: '20px', background: 'rgba(99,102,241,0.1)', borderRadius: '12px', border: '1px solid rgba(99,102,241,0.2)' }}>
        <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 600, marginBottom: '10px' }}>
            <Icon name="Book" size={16} style={{ marginRight: '8px' }} />Subject
        </label>
        <select value={plannerConfig.subject} onChange={e => setPlannerConfig({...plannerConfig, subject: e.target.value})}
            style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.3)', color: '#fff', fontSize: '1rem' }}>
            <option value="Civics">Civics</option>
            <option value="US History">US History</option>
            <option value="World History">World History</option>
            <option value="Geography">Geography</option>
            <option value="Economics">Economics</option>
        </select>
    </div>
</div>
```

### 3. Standards Browser
```javascript
{/* Standards Browser */}
<div style={{ marginBottom: '25px', padding: '20px', background: 'rgba(16,185,129,0.1)', borderRadius: '12px', border: '1px solid rgba(16,185,129,0.3)' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Icon name="Target" size={20} />
            {plannerConfig.state} Standards - Grade {plannerConfig.grade} {plannerConfig.subject}
        </h3>
        <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>
            {selectedStandards.length} selected
        </span>
    </div>
    
    <div style={{ maxHeight: '300px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {standards.map((std, i) => (
            <div key={i} onClick={() => toggleStandard(std.code)}
                style={{ 
                    padding: '15px', 
                    background: selectedStandards.includes(std.code) ? 'rgba(16,185,129,0.3)' : 'rgba(0,0,0,0.2)', 
                    borderRadius: '10px', 
                    border: selectedStandards.includes(std.code) ? '2px solid #10b981' : '1px solid rgba(255,255,255,0.1)',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                        <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#10b981' }}>{std.code}</span>
                        <p style={{ fontSize: '0.9rem', margin: '8px 0 0 0', color: 'rgba(255,255,255,0.8)' }}>{std.benchmark}</p>
                    </div>
                    {selectedStandards.includes(std.code) && (
                        <Icon name="CheckCircle" size={20} style={{ color: '#10b981', flexShrink: 0 }} />
                    )}
                </div>
                {std.topics && (
                    <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {std.topics.map((topic, j) => (
                            <span key={j} style={{ padding: '3px 8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', fontSize: '0.75rem' }}>
                                {topic}
                            </span>
                        ))}
                    </div>
                )}
            </div>
        ))}
    </div>
</div>
```

### 4. Unit Configuration
```javascript
{/* Unit Configuration */}
<div style={{ marginBottom: '25px', padding: '20px', background: 'rgba(251,191,36,0.1)', borderRadius: '12px', border: '1px solid rgba(251,191,36,0.3)' }}>
    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Icon name="Calendar" size={20} />Unit Configuration
    </h3>
    
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '15px', marginBottom: '15px' }}>
        <div>
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '6px', color: 'rgba(255,255,255,0.6)' }}>Unit Title</label>
            <input type="text" value={unitConfig.title} onChange={e => setUnitConfig({...unitConfig, title: e.target.value})}
                placeholder="e.g., Foundations of American Government"
                style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.3)', color: '#fff', fontSize: '1rem' }} />
        </div>
        <div>
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '6px', color: 'rgba(255,255,255,0.6)' }}>Duration (Days)</label>
            <input type="number" value={unitConfig.duration} onChange={e => setUnitConfig({...unitConfig, duration: parseInt(e.target.value) || 5})}
                min="1" max="20"
                style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.3)', color: '#fff', fontSize: '1rem' }} />
        </div>
        <div>
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '6px', color: 'rgba(255,255,255,0.6)' }}>Start Date</label>
            <input type="date" value={unitConfig.startDate} onChange={e => setUnitConfig({...unitConfig, startDate: e.target.value})}
                style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.3)', color: '#fff', fontSize: '1rem' }} />
        </div>
    </div>
    
    <button onClick={generateLessonPlan} disabled={plannerLoading || selectedStandards.length === 0}
        style={{ 
            padding: '14px 30px', borderRadius: '10px', border: 'none',
            background: (plannerLoading || selectedStandards.length === 0) ? 'rgba(255,255,255,0.1)' : 'linear-gradient(135deg, #f59e0b, #d97706)',
            color: '#fff', fontSize: '1rem', fontWeight: 700, cursor: (plannerLoading || selectedStandards.length === 0) ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', gap: '10px'
        }}>
        {plannerLoading ? (
            <><span style={{ animation: 'spin 1s linear infinite', display: 'inline-flex' }}><Icon name="Loader2" size={20} /></span>Generating...</>
        ) : (
            <><Icon name="Sparkles" size={20} />Generate {unitConfig.duration}-Day Lesson Plan</>
        )}
    </button>
</div>
```

### 5. Generated Lesson Plan Display
```javascript
{/* Generated Lesson Plan */}
{lessonPlan && (
    <div style={{ padding: '20px', background: 'rgba(99,102,241,0.1)', borderRadius: '12px', border: '1px solid rgba(99,102,241,0.3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Icon name="FileText" size={22} />{lessonPlan.title}
            </h3>
            <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={exportLessonPlanToWord} style={{ padding: '10px 20px', borderRadius: '8px', border: '2px solid rgba(99,102,241,0.5)', background: 'transparent', color: '#a5b4fc', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Icon name="Download" size={16} />Export to Word
                </button>
                <button onClick={createAssignmentsFromPlan} style={{ padding: '10px 20px', borderRadius: '8px', border: 'none', background: 'linear-gradient(135deg, #10b981, #059669)', color: '#fff', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Icon name="Plus" size={16} />Create Assignments
                </button>
            </div>
        </div>
        
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
            {lessonPlan.standards.map((code, i) => (
                <span key={i} style={{ padding: '4px 10px', background: 'rgba(16,185,129,0.2)', borderRadius: '6px', fontSize: '0.8rem', color: '#10b981' }}>
                    {code}
                </span>
            ))}
        </div>
        
        {/* Daily Lessons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {lessonPlan.days.map((day, i) => (
                <div key={i} style={{ padding: '20px', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                        <h4 style={{ fontSize: '1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ background: '#6366f1', color: '#fff', borderRadius: '50%', width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.85rem' }}>
                                {i + 1}
                            </span>
                            {day.title}
                        </h4>
                        <button onClick={() => editDay(i)} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: 'transparent', color: 'rgba(255,255,255,0.6)', cursor: 'pointer', fontSize: '0.85rem' }}>
                            <Icon name="Edit2" size={14} />
                        </button>
                    </div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                        {/* Bell Ringer */}
                        <div style={{ padding: '12px', background: 'rgba(251,191,36,0.1)', borderRadius: '8px', borderLeft: '3px solid #fbbf24' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#fbbf24', textTransform: 'uppercase' }}>Bell Ringer</span>
                            <p style={{ fontSize: '0.9rem', margin: '6px 0 0 0' }}>{day.bellRinger}</p>
                        </div>
                        
                        {/* Mini Lesson */}
                        <div style={{ padding: '12px', background: 'rgba(99,102,241,0.1)', borderRadius: '8px', borderLeft: '3px solid #6366f1' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a5b4fc', textTransform: 'uppercase' }}>Mini Lesson ({day.miniLessonTime})</span>
                            <p style={{ fontSize: '0.9rem', margin: '6px 0 0 0' }}>{day.miniLesson}</p>
                        </div>
                        
                        {/* Activity */}
                        <div style={{ padding: '12px', background: 'rgba(16,185,129,0.1)', borderRadius: '8px', borderLeft: '3px solid #10b981' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#10b981', textTransform: 'uppercase' }}>Activity</span>
                            <p style={{ fontSize: '0.9rem', margin: '6px 0 0 0' }}>{day.activity}</p>
                        </div>
                        
                        {/* Exit Ticket */}
                        <div style={{ padding: '12px', background: 'rgba(239,68,68,0.1)', borderRadius: '8px', borderLeft: '3px solid #ef4444' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#f87171', textTransform: 'uppercase' }}>Exit Ticket</span>
                            <p style={{ fontSize: '0.9rem', margin: '6px 0 0 0' }}>{day.exitTicket}</p>
                        </div>
                    </div>
                    
                    {day.homework && (
                        <div style={{ marginTop: '12px', padding: '10px 12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Icon name="Home" size={14} style={{ color: 'rgba(255,255,255,0.5)' }} />
                            <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)' }}>Homework: {day.homework}</span>
                        </div>
                    )}
                    
                    {day.materials && day.materials.length > 0 && (
                        <div style={{ marginTop: '10px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            {day.materials.map((mat, j) => (
                                <span key={j} style={{ padding: '3px 8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', fontSize: '0.75rem' }}>
                                    {mat}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            ))}
        </div>
    </div>
)}
```

---

## New Functions to Add

### 1. Toggle Standard Selection
```javascript
// Add after existing functions (around line 310)

const toggleStandard = (code) => {
    if (selectedStandards.includes(code)) {
        setSelectedStandards(selectedStandards.filter(c => c !== code));
    } else {
        setSelectedStandards([...selectedStandards, code]);
    }
};
```

### 2. Generate Lesson Plan (calls API)
```javascript
const generateLessonPlan = async () => {
    if (selectedStandards.length === 0) {
        alert('Please select at least one standard');
        return;
    }
    
    setPlannerLoading(true);
    
    try {
        const res = await fetch('/api/generate-lesson-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                state: plannerConfig.state,
                grade: plannerConfig.grade,
                subject: plannerConfig.subject,
                standards: selectedStandards,
                standardDetails: standards.filter(s => selectedStandards.includes(s.code)),
                unitTitle: unitConfig.title,
                duration: unitConfig.duration,
                startDate: unitConfig.startDate
            })
        });
        
        const data = await res.json();
        if (data.error) {
            alert('Error generating plan: ' + data.error);
        } else {
            setLessonPlan(data.plan);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        setPlannerLoading(false);
    }
};
```

### 3. Export to Word
```javascript
const exportLessonPlanToWord = async () => {
    if (!lessonPlan) return;
    
    try {
        const res = await fetch('/api/export-lesson-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan: lessonPlan })
        });
        
        const data = await res.json();
        if (data.path) {
            alert('Lesson plan exported to: ' + data.path);
        }
    } catch (err) {
        alert('Error exporting: ' + err.message);
    }
};
```

### 4. Create Assignments from Plan
```javascript
const createAssignmentsFromPlan = () => {
    if (!lessonPlan) return;
    
    // Switch to builder tab with pre-filled data
    setActiveTab('builder');
    setAssignment({
        ...assignment,
        title: lessonPlan.title + ' - Assessment',
        subject: plannerConfig.subject,
        instructions: 'Assessment for unit: ' + lessonPlan.title,
        gradingNotes: 'Standards covered: ' + lessonPlan.standards.join(', ')
    });
};
```

### 5. Load Standards on Config Change
```javascript
// Add useEffect to load standards when config changes
React.useEffect(() => {
    loadStandards();
}, [plannerConfig.state, plannerConfig.grade, plannerConfig.subject]);

const loadStandards = async () => {
    try {
        const res = await fetch('/api/get-standards', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                state: plannerConfig.state,
                grade: plannerConfig.grade,
                subject: plannerConfig.subject
            })
        });
        const data = await res.json();
        setStandards(data.standards || []);
        setSelectedStandards([]);  // Clear selection when changing config
    } catch (err) {
        console.error('Error loading standards:', err);
        setStandards([]);
    }
};
```

---

## New API Endpoints

### 1. GET Standards Endpoint
```python
# Add after existing endpoints (around line 1700)

@app.route('/api/get-standards', methods=['POST'])
def get_standards():
    """Get state standards for grade/subject."""
    data = request.json
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', 'Civics')
    
    # Florida B.E.S.T. Standards Database
    STANDARDS_DB = {
        "FL": {
            "Civics": {
                "7": [
                    {
                        "code": "SS.7.CG.1.1",
                        "benchmark": "Analyze the influences of ancient Greece, Rome, and the Judeo-Christian tradition on America's constitutional republic.",
                        "topics": ["Ancient Greece", "Roman Republic", "Judeo-Christian values", "Natural law"]
                    },
                    {
                        "code": "SS.7.CG.1.2",
                        "benchmark": "Trace the impact that the Magna Carta, English Bill of Rights, Mayflower Compact, and Thomas Paine's Common Sense had on the Declaration of Independence.",
                        "topics": ["Magna Carta", "English Bill of Rights", "Mayflower Compact", "Common Sense"]
                    },
                    {
                        "code": "SS.7.CG.1.3",
                        "benchmark": "Explain how the ideas expressed in the Declaration of Independence contributed to the American Revolution and the framework of American government.",
                        "topics": ["Declaration of Independence", "Natural rights", "Social contract", "Consent"]
                    },
                    {
                        "code": "SS.7.CG.1.4",
                        "benchmark": "Analyze the ideas of Hobbes, Locke, and Montesquieu, explain their contributions to the foundation of American government.",
                        "topics": ["Hobbes", "Locke", "Montesquieu", "Separation of powers", "Social contract"]
                    },
                    {
                        "code": "SS.7.CG.2.1",
                        "benchmark": "Explain the strengths, weaknesses, and consequences of the Articles of Confederation.",
                        "topics": ["Articles of Confederation", "Weaknesses", "Shays' Rebellion", "Constitutional Convention"]
                    },
                    {
                        "code": "SS.7.CG.2.2",
                        "benchmark": "Analyze the arguments of the Federalists and Anti-Federalists during the Constitutional Convention.",
                        "topics": ["Federalists", "Anti-Federalists", "Federalist Papers", "Bill of Rights"]
                    },
                    {
                        "code": "SS.7.CG.2.3",
                        "benchmark": "Explain the structure, functions, and processes of the legislative branch.",
                        "topics": ["Congress", "House", "Senate", "How a bill becomes law"]
                    },
                    {
                        "code": "SS.7.CG.2.4",
                        "benchmark": "Explain the structure, functions, and processes of the executive branch.",
                        "topics": ["President", "Executive agencies", "Cabinet", "Presidential powers"]
                    },
                    {
                        "code": "SS.7.CG.2.5",
                        "benchmark": "Explain the structure, functions, and processes of the judicial branch.",
                        "topics": ["Supreme Court", "Federal courts", "Judicial review", "Marbury v Madison"]
                    },
                    {
                        "code": "SS.7.CG.2.6",
                        "benchmark": "Analyze the Constitution for application of the principles of federalism, separation of powers, checks and balances, and individual rights.",
                        "topics": ["Federalism", "Separation of powers", "Checks and balances", "Bill of Rights"]
                    },
                    {
                        "code": "SS.7.CG.3.1",
                        "benchmark": "Explain how the Constitution can be changed through the formal amendment process and the informal processes.",
                        "topics": ["Amendment process", "Formal amendments", "Informal changes", "Judicial interpretation"]
                    },
                    {
                        "code": "SS.7.CG.3.2",
                        "benchmark": "Identify the protections guaranteed by the Bill of Rights.",
                        "topics": ["1st Amendment", "2nd Amendment", "4th Amendment", "5th Amendment", "Rights"]
                    }
                ]
            },
            "US History": {
                "8": [
                    {
                        "code": "SS.8.A.1.1",
                        "benchmark": "Provide supporting details for an answer from text, interview for oral history, or other primary sources.",
                        "topics": ["Primary sources", "Evidence", "Historical analysis"]
                    },
                    {
                        "code": "SS.8.A.2.1",
                        "benchmark": "Compare the relationships among the British, French, Spanish, and Dutch in their struggle for colonization of North America.",
                        "topics": ["Colonial powers", "Competition", "Settlement patterns"]
                    }
                    # Add more standards...
                ]
            }
        }
    }
    
    try:
        standards = STANDARDS_DB.get(state, {}).get(subject, {}).get(grade, [])
        return jsonify({"standards": standards})
    except:
        return jsonify({"standards": []})
```

### 2. Generate Lesson Plan Endpoint
```python
@app.route('/api/generate-lesson-plan', methods=['POST'])
def generate_lesson_plan():
    """Generate AI lesson plan based on standards."""
    data = request.json
    
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', 'Civics')
    standards = data.get('standards', [])
    standard_details = data.get('standardDetails', [])
    unit_title = data.get('unitTitle', '')
    duration = data.get('duration', 5)
    
    # Build standards context
    standards_text = ""
    for std in standard_details:
        standards_text += f"\n- {std['code']}: {std['benchmark']}"
        if std.get('topics'):
            standards_text += f"\n  Topics: {', '.join(std['topics'])}"
    
    prompt = f"""You are an expert {subject} teacher creating a {duration}-day unit plan for {grade}th grade students.

STATE STANDARDS TO COVER:
{standards_text}

UNIT TITLE: {unit_title or 'Generate an appropriate title'}

Create an engaging, detailed {duration}-day lesson plan. For EACH day, provide:

1. A descriptive title for the day's lesson
2. Bell Ringer (5 min warm-up question/activity)
3. Mini Lesson topic and duration (10-15 min direct instruction)
4. Main Activity (20-25 min student-centered activity - make these ENGAGING and VARIED: debates, simulations, group work, primary source analysis, creative projects, etc.)
5. Exit Ticket (5 min check for understanding)
6. Homework assignment (optional, meaningful practice)
7. Materials needed

IMPORTANT GUIDELINES:
- Make activities ENGAGING and AGE-APPROPRIATE for {grade}th graders
- Include a MIX of activity types (not just worksheets)
- Build knowledge progressively across the {duration} days
- Include at least one assessment opportunity
- Vary the activities: include discussions, simulations, group work, debates, creative projects
- Be specific with instructions

Return your response as JSON in this exact format:
{{
    "title": "Unit Title",
    "standards": ["SS.7.CG.1.1", "SS.7.CG.1.2"],
    "days": [
        {{
            "day": 1,
            "title": "Day 1 Title",
            "bellRinger": "Question or activity",
            "miniLesson": "Topic and key points",
            "miniLessonTime": "15 min",
            "activity": "Detailed activity description",
            "exitTicket": "Assessment question",
            "homework": "Assignment or null",
            "materials": ["item1", "item2"]
        }}
    ]
}}"""

    try:
        from openai import OpenAI
        client = OpenAI()
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert curriculum designer. Return ONLY valid JSON, no markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean up response if needed
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()
        
        import json
        plan = json.loads(result)
        
        return jsonify({"plan": plan})
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()})
```

### 3. Export Lesson Plan to Word
```python
@app.route('/api/export-lesson-plan', methods=['POST'])
def export_lesson_plan():
    """Export lesson plan to Word document."""
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    data = request.json
    plan = data.get('plan', {})
    
    try:
        doc = Document()
        
        # Title
        title = doc.add_heading(plan.get('title', 'Lesson Plan'), 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Standards
        doc.add_heading('Standards Covered', level=1)
        for std in plan.get('standards', []):
            doc.add_paragraph(std, style='List Bullet')
        
        # Daily Plans
        for day in plan.get('days', []):
            doc.add_heading(f"Day {day['day']}: {day['title']}", level=1)
            
            # Bell Ringer
            doc.add_heading('Bell Ringer (5 min)', level=2)
            doc.add_paragraph(day.get('bellRinger', ''))
            
            # Mini Lesson
            doc.add_heading(f"Mini Lesson ({day.get('miniLessonTime', '15 min')})", level=2)
            doc.add_paragraph(day.get('miniLesson', ''))
            
            # Activity
            doc.add_heading('Activity', level=2)
            doc.add_paragraph(day.get('activity', ''))
            
            # Exit Ticket
            doc.add_heading('Exit Ticket (5 min)', level=2)
            doc.add_paragraph(day.get('exitTicket', ''))
            
            # Homework
            if day.get('homework'):
                doc.add_heading('Homework', level=2)
                doc.add_paragraph(day.get('homework', ''))
            
            # Materials
            if day.get('materials'):
                doc.add_heading('Materials', level=2)
                for mat in day.get('materials', []):
                    doc.add_paragraph(mat, style='List Bullet')
            
            doc.add_page_break()
        
        # Save
        output_path = f"/Users/alexc/Downloads/Graider/Lesson_Plans/{plan.get('title', 'Lesson_Plan').replace(' ', '_')}.docx"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        
        return jsonify({"path": output_path})
        
    except Exception as e:
        return jsonify({"error": str(e)})
```

---

## Tab Navigation Update

```javascript
// Update the tab buttons (around line 450)
// Add 'planner' to the tabs array

{['home', 'results', 'emails', 'builder', 'planner', 'settings'].map(tab => (
    <button key={tab} onClick={() => setActiveTab(tab)}
        style={{ 
            padding: '12px 24px', 
            borderRadius: '10px', 
            border: 'none',
            background: activeTab === tab ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'transparent',
            color: activeTab === tab ? '#fff' : 'rgba(255,255,255,0.6)',
            fontSize: '0.95rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
        }}>
        <Icon name={
            tab === 'home' ? 'Home' : 
            tab === 'results' ? 'BarChart3' : 
            tab === 'emails' ? 'Mail' : 
            tab === 'builder' ? 'Wrench' : 
            tab === 'planner' ? 'BookOpen' :
            'Settings'
        } size={18} />
        {tab.charAt(0).toUpperCase() + tab.slice(1)}
    </button>
))}
```

---

## Implementation Order

### Phase 1: Basic Infrastructure
1. Add new state variables
2. Add Planner tab navigation
3. Add configuration selectors (state/grade/subject)

### Phase 2: Standards Database
4. Create `/api/get-standards` endpoint with Florida Civics standards
5. Add standards browser UI
6. Implement standard selection toggle

### Phase 3: Lesson Generation
7. Create `/api/generate-lesson-plan` endpoint
8. Add unit configuration UI
9. Implement generateLessonPlan function
10. Add lesson plan display UI

### Phase 4: Export & Integration
11. Create `/api/export-lesson-plan` endpoint
12. Add export to Word button
13. Add create assignments from plan function
14. Connect to Builder tab

### Phase 5: Expansion
15. Add more Florida standards (US History, Geography)
16. Add other state standards
17. Add lesson editing capability
18. Add saved plans management

---

## File Changes Summary

| File | Changes |
|------|---------|
| `graider_app.py` | Add state variables (~line 224) |
| `graider_app.py` | Add helper functions (~line 310) |
| `graider_app.py` | Update tab navigation (~line 450) |
| `graider_app.py` | Add Planner tab content (~line 1100) |
| `graider_app.py` | Add `/api/get-standards` endpoint (~line 1700) |
| `graider_app.py` | Add `/api/generate-lesson-plan` endpoint (~line 1750) |
| `graider_app.py` | Add `/api/export-lesson-plan` endpoint (~line 1850) |

---

## Estimated Lines of Code

| Component | Lines |
|-----------|-------|
| State variables | ~20 |
| Helper functions | ~60 |
| Tab navigation update | ~5 |
| Planner tab UI | ~300 |
| Standards endpoint | ~100 |
| Generate plan endpoint | ~100 |
| Export endpoint | ~80 |
| **Total new code** | **~665 lines** |

---

## Ready to Implement?

This plan provides:
- ✅ Standards browser for Florida Civics
- ✅ AI-generated lesson plans
- ✅ Day-by-day breakdown with activities
- ✅ Export to Word
- ✅ Integration with Assignment Builder

Say "go" and I'll implement Phase 1-4!
