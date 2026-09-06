(()=>{const target=document.querySelector('.capabilities .wrap');if(!target)return;const industries=[
['💼','Business & Accounting','Accounting, invoicing, payroll support, CRM, ERP, cashflow and operations'],
['🛒','E-Commerce & Retail','Online stores, marketplaces, POS support, stock, loyalty and order management'],
['🏦','Banking, Finance & Insurance','Financial dashboards, payments, claims, portfolio analytics and governed fintech workflows'],
['🏥','Healthcare & Clinics','Appointments, clinic operations, queues, records workflow and administration'],
['✈️','Tourism & Hospitality','Tour booking, itineraries, guide apps, reservations, rooms and housekeeping'],
['🍽️','Food & Beverage','Restaurant ordering, menu systems, kitchen workflow and delivery management'],
['🏭','Manufacturing & Industrial','Production tracking, maintenance, QC, work orders and factory dashboards'],
['🌾','Agriculture & Plantation','Farm management, plantation GIS, crop monitoring, livestock and field records'],
['🏗️','Construction & Property','Project tracking, site diary, BOQ support, property systems and inspections'],
['🚚','Logistics & Transportation','Fleet, delivery tracking, dispatch, route planning, warehouse and scheduling'],
['🏛️','Government & Public Service','Administration, HR, procurement, permits, complaints, assets and case management'],
['🎓','Education & Training','LMS, student portals, attendance, assessment, tuition and learning analytics'],
['📍','GIS, Surveying & Geospatial','Web GIS, cadastral tools, GNSS field apps, mapping, LiDAR/UAV and asset GIS'],
['⚡','Energy & Utilities','Solar, utility dashboards, meter analytics, maintenance and field inspection'],
['🤝','Professional Services','Consulting, quotations, client portals, project delivery, appointments and workflow systems'],
['⚖️','Legal & Compliance','Case tracking, contract workflow, audit, evidence, policy and compliance systems'],
['🎬','Media & Creative Industry','CMS, newsroom workflow, content studio, digital assets and creator platforms'],
['🚗','Automotive & Fleet','Workshop management, vehicle maintenance, parts inventory and telematics'],
['🧠','Technology, AI & Automation','AI assistants, agents, APIs, SaaS, automation, IoT and data platforms'],
['🧩','Other Malaysian Industries','Custom systems for specialised sectors, associations, communities and emerging industries']
];
const featuredCount=6;
target.innerHTML=`<div class="section-title"><div><h2>What can VL build?</h2><p>One governed software factory across Malaysia’s public and private sector industries.</p></div><a class="outline" href="./capabilities.html">Explore all industries →</a></div><div class="cap-grid" id="industryGrid">${industries.map((i,n)=>`<div class="cap${n>=featuredCount?' industry-extra':''}"><div class="ico">${i[0]}</div><div><strong>${i[1]}</strong><small>${i[2]}</small></div></div>`).join('')}</div><button class="industry-toggle" id="industryToggle" type="button" aria-expanded="false" aria-controls="industryGrid">View all 20 industries ↓</button>`;
const btn=document.getElementById('industryToggle');if(!btn)return;btn.addEventListener('click',()=>{const open=target.classList.toggle('industries-open');btn.setAttribute('aria-expanded',String(open));btn.textContent=open?'Show featured industries ↑':'View all 20 industries ↓';if(!open)target.scrollIntoView({behavior:'smooth',block:'start'});});
})();