# Phase 2 & 3 Implementation Plan

## Phase 2: Admin Functions (Rank 3+)

### Channel Customization
- [ ] `setMotd` - Set message of the day
- [ ] `setChannelCSS` - Set custom CSS (max 20KB)
- [ ] `setChannelJS` - Set custom JavaScript (max 20KB)

### Channel Options
- [ ] `setOptions` - Update channel options
  - voteskip_ratio
  - afk_timeout
  - pagetitle
  - externalcss
  - externaljs
  - chat_antiflood
  - chat_antiflood_params (burst, sustained, cooldown)
  - show_public
  - enable_link_regex
  - password (rank 3+)
  - allow_voteskip
  - maxlength (max video duration)
  - And many more...

### Permissions
- [ ] `setPermissions` - Update permission levels for actions
- [ ] `togglePlaylistLock` - Lock/unlock playlist

### Emote Management
- [ ] `updateEmote` - Add or update channel emote
- [ ] `removeEmote` - Remove channel emote
- [ ] `requestEmoteList` - Get current emote list (already auto-sent on join)

### Chat Filters
- [ ] `addFilter` - Add chat filter (regex-based)
- [ ] `updateFilter` - Update existing filter
- [ ] `removeFilter` - Remove filter
- [ ] `requestChatFilters` - Get filter list

## Phase 3: Advanced Admin (Rank 3-4+)

### Poll Management (Rank 2+)
- [ ] `newPoll` - Create new poll
- [ ] `vote` - Vote in active poll  
- [ ] `closePoll` - Close active poll

### Channel Ranks (Rank 4+)
- [ ] `setChannelRank` - Set user's permanent channel rank
- [ ] `requestChannelRanks` - Get list of channel moderators/admins

### Ban Management (Rank 3+)
- [ ] `requestBanlist` - Get list of banned users
- [ ] `unban` - Remove ban from user

### Channel Log (Rank 3+)
- [ ] `readChanLog` - Read channel event log

### User Library (Rank varies)
- [ ] `searchLibrary` - Search channel library
- [ ] `deleteFromLibrary` - Delete item from library (rank 2+)

## Implementation Status

### Completed
✅ Phase 1: Core moderator functions (rank 2)
✅ Phase 4: Profile extraction

### In Progress
🔄 Phase 2: Admin functions (rank 3)

### To Do
⏳ Phase 3: Advanced admin (rank 3-4+)
⏳ Documentation and tests

## Notes

- All Socket.IO events will be added to CytubeEventSender
- All commands will be routed via CommandSubscriber
- All methods will be added to kryten-py KrytenClient
- Rank requirements will be documented in docstrings
- Large payloads (CSS/JS) should be validated for size limits
