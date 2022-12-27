cat << EOF > logo_review.html
<html>
<head>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.0.0/dist/css/bootstrap.min.css" integrity="sha384-Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm" crossorigin="anonymous">
<style>
.applogo img {
  mask: url(#masking);
  background-color: #f9f9f9;
}

.applogo {
  filter: drop-shadow(0 3px 3px rgba(0,0,0,.2)) drop-shadow(0 3px 3px rgba(0,0,0,.2));
}
</style>

<svg width="0" height="0" viewBox="0 0 200 200">
  <defs>
    <mask id="masking">
      <path fill="white" d="M 0 100 C 0 10 10 0 100 0 C 190 0 200 10 200 100 C 200 190 190 200 100 200 C 10 200 0 190 0 100 Z" />
    </mask>
  </defs>
</svg>
</head>

<body>
<div class="row">
EOF


for APP in $(cat ../apps.json  | jq -r '.[] | select ( .state=="working" ) | .url'  | awk -F/ '{print $NF}' | sed 's/_ynh//g' | tr 'A-Z' 'a-z')
do

    ls $APP.* >/dev/null 2>/dev/null || { echo "Missingfor $APP" && continue; }

    cat << EOF >> logo_review.html
<div class="col-1 text-center" >
EOF
  # <h2 style="font-weight: bold; margin-top: 2em;">$APP</h2>

   for FILE in $(ls $APP.* 2>/dev/null)
   do
    cat << EOF >> logo_review.html
<div class="applogo">
<img src="$FILE" width="200" height="200" />
</div>
EOF

   done

   echo "</div>" >> logo_review.html
done

cat << EOF >> logo_review.html
</div>
</body>
</html>
EOF
