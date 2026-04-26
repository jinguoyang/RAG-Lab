# RAG Platform Design System

Claude-inspired design system for the RAG debugging platform backend interface.

## Overview

This design system provides a warm, professional, and high-information-density interface for knowledge workers. It balances Claude's editorial aesthetic with the functional needs of a complex admin system.

## Design Philosophy

- **Warm & Professional**: Uses parchment backgrounds and terracotta accents instead of cold grays
- **Editorial Not Marketing**: Serif headings, clean layouts, minimal decoration
- **High Density**: Optimized for information-dense interfaces while maintaining clarity
- **Traceable**: Clear visual hierarchy for documents, chunks, evidence, and relationships

## Color System

### Base Colors
- `--parchment` (#f5f4ed) - Global page background
- `--ivory` (#faf9f5) - Card/table surfaces
- `--terracotta` (#c96442) - Primary actions, active states
- `--near-black` (#141413) - Primary text
- `--olive-gray` (#5e5d59) - Secondary text
- `--stone-gray` (#87867f) - Tertiary text
- `--border-cream` (#f0eee6) - Light borders
- `--border-warm` (#e8e6dc) - Visible borders

### Status Colors
- `--success-green` (#4a7c59) - Success states
- `--error-red` (#b53333) - Error states
- `--warning-amber` (#d4a574) - Warning/partial states
- `--info-blue` (#5b8ba8) - Informational states
- `--focus-blue` (#3898ec) - Focus rings (accessibility)

## Typography

### Font Families
- **Serif**: Georgia - Used for page titles, section headers, card titles
- **Sans**: System fonts - Used for all UI elements, buttons, forms
- **Mono**: SF Mono/Consolas - Used for IDs, traces, code

### Font Sizes
- Page Title: 32px (h1)
- Section Title: 24px (h2)
- Card Title: 20px (h3)
- Body: 16px (default)
- Caption: 14px
- Label: 12px

### Usage Rules
- Headings (h1-h3) always use serif
- All buttons, forms, tables, navigation use sans-serif
- Technical IDs (DocId, ChunkId, RunId) use monospace

## Components

### Core Components

#### Button
- Variants: primary, secondary, outline, ghost, destructive
- Sizes: sm (32px), md (40px), lg (48px)
- 10px border radius, focus ring on keyboard navigation

#### Badge & StatusBadge
- Lightweight status indicators with icon + text
- Never rely on color alone (includes icon)
- Variants: success, error, warning, info, queued, running, draft, saved, active, inactive

#### Card
- Ivory surface with cream border
- 12px border radius
- Subtle warm ring shadow
- Sections: Header, Content, Footer

#### Table
- 44-48px row height
- Sticky header
- Warm borders, no zebra striping
- Hover state for interactive rows

#### PageHeader
- Contains breadcrumbs, title, description, actions, context labels
- Serif title, sans-serif description
- Fixed at top of content area

#### Drawer
- Side panels for details
- Widths: 480px, 560px, 640px
- Ivory surface with sections

#### Timeline
- For job history, revision history, traces
- Shows status, timestamp, duration, operator
- Expandable details

#### Alert
- System messages and notifications
- Variants: info, success, warning, error, permission
- Left border accent, optional close button

#### Input
- Ivory background with cream border
- Blue focus ring
- Support for labels, errors, helper text

## Layout System

### Global Structure
- Left navigation: 240px
- Top context bar: 56-64px
- Main content: fluid with max-width

### Grid
- 12-column grid
- Design width: 1360-1440px
- High density, minimal whitespace

### Spacing
- Use 4px base unit
- Common values: 8px, 12px, 16px, 24px, 32px

### Border Radius
- Small: 8px
- Medium: 10px
- Default: 12px
- Large: 16px

## Usage Examples

```tsx
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  StatusBadge,
  Table,
  PageHeader
} from './components/rag';

// Page with header and cards
<>
  <PageHeader
    title="Knowledge Base Overview"
    description="Manage documents and configurations"
    actions={<Button variant="primary">New Document</Button>}
  />
  
  <Card>
    <CardHeader>
      <CardTitle>Recent Documents</CardTitle>
    </CardHeader>
    <CardContent>
      <Table>
        {/* table content */}
      </Table>
    </CardContent>
  </Card>
</>
```

## State Patterns

Every page should handle these states:
- **Loading**: Show skeleton/spinner
- **Empty**: Clear empty state with action
- **Error**: Error message with retry
- **Permission Denied**: Locked state with explanation
- **Partial Success**: Warning alert with details

## Accessibility

- All interactive elements have focus states
- Status badges include icons, not just color
- Sufficient color contrast (WCAG AA)
- Keyboard navigation supported
- Screen reader friendly labels

## File Organization

```
src/
├── app/
│   └── components/
│       └── rag/
│           ├── Alert.tsx
│           ├── Badge.tsx
│           ├── Button.tsx
│           ├── Card.tsx
│           ├── Drawer.tsx
│           ├── Input.tsx
│           ├── PageHeader.tsx
│           ├── Table.tsx
│           ├── Timeline.tsx
│           └── index.ts
└── styles/
    ├── theme.css (design tokens)
    └── fonts.css (font imports)
```

## What's Next

Use these components to build:
- P01: Login page
- P02-P04: Platform management pages
- P05: Knowledge base overview
- P06-P07: Document management
- P08: Configuration center
- P09: QA debugging page (most complex)
- P10: QA history
- P11: Graph retrieval analysis
- P12: Members & permissions
