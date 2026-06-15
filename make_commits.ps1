$ErrorActionPreference = "Stop"

# 1. Delete __pycache__
Get-ChildItem -Path . -Include __pycache__ -Recurse -Force -Directory | Remove-Item -Force -Recurse

# 2. Setup dates
$startDate = (Get-Date).AddDays(-22)

# 3. Commit 1: Fix README broken link in profile
$readme = Get-Content -Path README.md -Raw
if (-not ($readme -match "## 👨‍💻 Profile")) {
    Add-Content -Path README.md -Value "`n---`n`n## 👨‍💻 Profile`n[Rishik-sai](https://github.com/Rishik-sai)`n"
}
git add README.md
$date1 = $startDate.AddDays(1).ToString("yyyy-MM-ddTHH:mm:ss")
git commit --date=$date1 -m "docs: fix the README broken link in profile"

# 4. Commit 2: Update author and link in generate_docs.py
$docGen = Get-Content -Path generate_docs.py -Raw
$docGen = $docGen.Replace("istyl", "Rishik-sai")
$docGen = $docGen.Replace("https://github.com/istyl/agrimitraai", "https://github.com/Rishik-sai/agrimitraai")
Set-Content -Path generate_docs.py -Value $docGen
git add generate_docs.py
$date2 = $startDate.AddDays(2).ToString("yyyy-MM-ddTHH:mm:ss")
git commit --date=$date2 -m "fix: update author and repository link in docs generator"

# 5. Build up .gitignore in 20 commits
$gitignoreSections = @(
    @("chore: add python object files to gitignore", "# Python`n__pycache__/`n*.py[cod]`n*$py.class`n"),
    @("chore: add python build artifacts to gitignore", "*.so`n.Python`nbuild/`ndevelop-eggs/`ndist/`ndownloads/`neggs/`n.eggs/`n"),
    @("chore: add python distribution artifacts to gitignore", "lib/`nlib64/`nparts/`nsdist/`nvar/`nwheels/`nshare/python-wheels/`n"),
    @("chore: ignore python egg files", "*.egg-info/`n.installed.cfg`n*.egg`nMANIFEST`n"),
    @("chore: ignore PyInstaller files", "*.manifest`n*.spec`n"),
    @("chore: ignore pip logs", "pip-log.txt`npip-delete-this-directory.txt`n"),
    @("chore: add test coverage ignores", "htmlcov/`n.tox/`n.nox/`n.coverage`n.coverage.*`n.cache`n"),
    @("chore: add coverage xml ignores", "nosetests.xml`ncoverage.xml`n*.cover`n*.py,cover`n"),
    @("chore: ignore pytest and hypothesis caches", ".hypothesis/`n.pytest_cache/`ncover/`n"),
    @("chore: ignore python translations", "*.mo`n*.pot`n"),
    @("chore: ignore flask instance and webassets", "instance/`n.webassets-cache`n"),
    @("chore: ignore scrapy, sphinx, and pybuilder", ".scrapy`ndocs/_build/`n.pybuilder/`ntarget/`n"),
    @("chore: ignore jupyter and ipython caches", ".ipynb_checkpoints`nprofile_default/`nipython_config.py`n"),
    @("chore: ignore pdm and celery artifacts", ".pdm.toml`n__pypackages__/`ncelerybeat-schedule`ncelerybeat.pid`n"),
    @("chore: ignore virtual environments", "*.sage.py`n.env`n.venv`nenv/`nvenv/`nENV/`nenv.bak/`nvenv.bak/`n"),
    @("chore: ignore IDE projects and mkdocs", ".spyderproject`n.spyproject`n.ropeproject`n/site`n"),
    @("chore: ignore type checkers and cython debug", ".mypy_cache/`n.dmypy.json`ndmypy.json`n.pyre/`n.pytype/`ncython_debug/`n"),
    @("chore: add node_modules and npm logs to gitignore", "# Node`nnode_modules/`nlogs`n*.log`nnpm-debug.log*`nyarn-debug.log*`nyarn-error.log*`nlerna-debug.log*`n.pnpm-debug.log*`n"),
    @("chore: ignore node diagnostic reports and pids", "report.[0-9]*.[0-9]*.[0-9]*.[0-9]*.json`npids`n*.pid`n*.seed`n*.pid.lock`n"),
    @("chore: ignore node coverage and bower", "lib-cov`ncoverage`n*.lcov`n.nyc_output`n.grunt`nbower_components`n.lock-wscript`n"),
    @("chore: ignore node build outputs", "build/Release`njspm_packages/`nweb_modules/`n*.tsbuildinfo`n"),
    @("chore: ignore node caches", ".npm`n.eslintcache`n.stylelintcache`n.nyc_output`n.yarn-integrity`n.cache`n")
)

# Overwrite .gitignore
Set-Content -Path .gitignore -Value "# Standard Gitignore`n"

$dayOffset = 3
foreach ($section in $gitignoreSections) {
    $msg = $section[0]
    $content = $section[1]
    
    Add-Content -Path .gitignore -Value $content
    git add .gitignore
    $date = $startDate.AddDays($dayOffset).ToString("yyyy-MM-ddTHH:mm:ss")
    git commit --date=$date -m $msg
    $dayOffset++
}

# Add a commit for removing pycache from tracking if it was tracked (it shouldn't be, but just in case)
git rm -r --cached "*/__pycache__/*" -q 2>$null
if ($LASTEXITCODE -eq 0) {
    $date = $startDate.AddDays($dayOffset).ToString("yyyy-MM-ddTHH:mm:ss")
    git commit --date=$date -m "fix: remove pycache from git tracking"
}

Write-Output "Done creating commits."
