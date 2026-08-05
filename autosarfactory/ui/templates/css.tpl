<style>

/* This file has code generated using AI */

* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f8f9fa; color: #333; height: 100vh;
       display: flex; flex-direction: column; }

header { background: #1a1a2e; color: #fff; padding: .55rem 1rem;
         display: flex; align-items: center; gap: .75rem; flex-shrink: 0; }
header h1 { font-size: .95rem; font-weight: 600; white-space: nowrap; flex: 1; }
#search-wrap { position: relative; }
#search { padding: .28rem .6rem; border-radius: 4px; border: none;
          font-size: .86rem; width: 260px; }
#search-dropdown { display: none; position: absolute; top: 100%; left: 0; right: 0;
                   background: #fff; border: 1px solid #d1d5db; border-top: none;
                   border-radius: 0 0 6px 6px; max-height: 260px; overflow-y: auto;
                   list-style: none; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,.15); }
#search-dropdown li { padding: .35rem .6rem; cursor: pointer; font-size: .78rem;
                      color: #333; border-bottom: 1px solid #f0f0f0; display: flex;
                      justify-content: space-between; align-items: center; }
#search-dropdown li:hover, #search-dropdown li.active { background: #e8f0fe; }
#search-dropdown li .dd-path { font-size: .65rem; color: #999; margin-left: .3rem; }
#search-dropdown li .dd-tag { font-size: .65rem; color: #888; background: #f3f4f6;
                              border-radius: 3px; padding: .05rem .3rem; flex-shrink: 0; }
#match-count { font-size: .75rem; color: #99aacc; white-space: nowrap; }
#view-filter { padding: .28rem .4rem; border-radius: 4px; border: none;
               font-size: .8rem; background: #2e3a6e; color: #cce; cursor: pointer; }
#view-filter:hover { background: #3d4f9a; }
#sidebar-toggle { padding: .28rem .7rem; background: #2e3a6e; color: #cce;
                  border: none; border-radius: 4px; cursor: pointer;
                  font-size: .8rem; white-space: nowrap; }
#sidebar-toggle:hover { background: #3d4f9a; }

.main { display: flex; flex: 1; overflow: hidden; }

/* graph panel */
#graph-panel { flex: 1; overflow: hidden; position: relative; min-width: 0; }
#mynetwork { width: 100%; height: 100%; background: #fff; }

/* legend */
#legend { position: absolute; top: 12px; left: 12px;
          background: rgba(255,255,255,.93); border: 1px solid #ddd;
          border-radius: 6px; padding: 8px 12px;
          font-size: .76rem; color: #555;
          display: flex; flex-direction: column; gap: 6px;
          pointer-events: none; }
.legend-item { display: flex; align-items: center; gap: 8px; }
.leg-dot    { display:inline-block; width:10px; height:10px; border-radius:50%;
              border:2px solid; margin:0 13px 0 13px; }
.leg-solid  { display:inline-block; width:36px; height:2px; background:#aaa; }
.leg-dashed { display:inline-block; width:36px; height:2px;
              background: repeating-linear-gradient(90deg,#e67e22 0,#e67e22 6px,transparent 6px,transparent 10px); }

#reset-btn { position: absolute; bottom: .75rem; right: .75rem;
             padding: .3rem .68rem; background: #1a1a2e; color: #fff;
             border: none; border-radius: 4px; cursor: pointer;
             font-size: .75rem; opacity: .6; transition: opacity .15s; }
#reset-btn:hover { opacity: 1; }

/* sidebar */
#sidebar { width: 340px; display: flex; flex-direction: column;
           background: #fff; border-left: 1px solid #e0e0e0; flex-shrink: 0;
           transition: width .22s ease, opacity .22s ease; overflow: hidden; }
#sidebar.collapsed { width: 0; opacity: 0; pointer-events: none; }

/* properties panel */
#prop-panel { flex: 1; overflow-y: auto; }

#prop-placeholder { padding: 1.2rem 1rem; color: #999; }
#prop-placeholder p { font-size: .82rem; line-height: 1.6; margin-bottom: .6rem; }
.hint-small { font-size: .74rem; color: #bbb; line-height: 1.7; }

#prop-content { display: none; }

#prop-header { padding: .75rem 1rem .5rem; border-bottom: 1px solid #eee; }
#prop-name { font-size: .95rem; font-weight: 700; color: #1a1a2e; word-break: break-all; }
#prop-meta { margin-top: .25rem; }
#prop-meta .type-badge { display: inline-block; background: #e8f0fe; color: #1a1a2e;
                          border-radius: 3px; padding: .1rem .4rem;
                          font-size: .7rem; font-weight: 600; }
#prop-path { margin-top: .3rem; font-size: .72rem; color: #888;
             word-break: break-all; line-height: 1.4; }

.prop-section-title { padding: .4rem 1rem .2rem; font-size: .7rem; font-weight: 700;
                       text-transform: uppercase; letter-spacing: .06em; color: #999;
                       background: #f8f9fa; border-bottom: 1px solid #eee; }

table { border-collapse: collapse; width: 100%; font-size: .78rem; }
th, td { border-bottom: 1px solid #f0f0f0; padding: .28rem .6rem; text-align: left; }
th { background: #fafafa; font-weight: 600; color: #555; font-size: .72rem; position: sticky; top: 0; z-index: 1; }
tr:hover td { background: #f5f8ff; }
td.prop-key  { color: #555; width: 42%; font-size: .75rem; }
td.prop-val  { color: #222; word-break: break-all; }
td code { font-size: .72rem; color: #c0392b; }

#prop-refs-section { display: none; }
#prop-refs-table td { font-size: .75rem; }
#prop-refs-table td a { color: #3b82f6; text-decoration: none; cursor: pointer; }
#prop-refs-table td a:hover { text-decoration: underline; }

#prop-refby-section { display: none; }
#prop-refby-table td { font-size: .75rem; }
#prop-refby-table td a { color: #3b82f6; text-decoration: none; cursor: pointer; }
#prop-refby-table td a:hover { text-decoration: underline; }

/* "Show in tree" button */
.show-in-tree-btn { display: inline-block; margin-top: .35rem; padding: .22rem .55rem;
                    background: #7c3aed; color: #fff; border: none; border-radius: 4px;
                    font-size: .72rem; cursor: pointer; transition: background .15s; }
.show-in-tree-btn:hover { background: #6d28d9; }

/* context menu */
#ctx-menu { display: none; position: fixed; z-index: 200; background: #fff;
            border: 1px solid #d1d5db; border-radius: 6px; padding: .3rem 0;
            box-shadow: 0 4px 12px rgba(0,0,0,.15); min-width: 180px; }
#ctx-menu li { list-style: none; padding: .35rem .8rem; font-size: .78rem;
               cursor: pointer; color: #333; }
#ctx-menu li:hover { background: #e8f0fe; }
#ctx-menu li.ctx-sep { border-top: 1px solid #eee; margin-top: .2rem; padding-top: .4rem; }

/* orphan badge in properties panel */
.orphan-badge { display: inline-block; background: #fef3c7; color: #92400e;
                border-radius: 3px; padding: .1rem .4rem; margin-left: .3rem;
                font-size: .65rem; font-weight: 600; vertical-align: middle; }
</style>
