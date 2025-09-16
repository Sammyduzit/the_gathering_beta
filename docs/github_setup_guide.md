# 🚀 GitHub Repository Setup Guide

## Schritt 1: Alte Repository-Verbindung trennen

```bash
# Aktuelle Git-Konfiguration prüfen
git remote -v

# Alte Origin entfernen (behält lokale Geschichte)
git remote remove origin

# Lokalen Git-Status prüfen
git status
```

## Schritt 2: Neue GitHub Repository erstellen

### Option A: Über GitHub Web Interface
1. Gehe zu https://github.com/new
2. Repository Name: `the-gathering-ai` (oder gewünschter Name)
3. Description: `FastAPI chat application with AI entities using Langchain`
4. **WICHTIG:** Repository als **Private** markieren (AI-Integration, persönliches Projekt)
5. **NICHT** README, .gitignore oder LICENSE hinzufügen (lokale Dateien behalten)
6. Repository erstellen

### Option B: Über GitHub CLI (falls installiert)
```bash
gh repo create the-gathering-ai --private --description "FastAPI chat application with AI entities using Langchain"
```

## Schritt 3: Lokale Änderungen committen

```bash
# Aktuelle Änderungen (Aufräumung + sichere .env.example) committen
git add .
git status  # Prüfen was committed wird

# Commit mit Aufräumung
git commit -m "Projekt-Aufräumung: redundante Dateien entfernt, sichere .env.example erstellt

- Entfernt: __test/, __old/, Präsi/, htmlcov/, caches
- Sicherheit: .env.example mit Platzhaltern und Anweisungen
- Behalten: sonar-project.properties für CI/CD Quality Gates"
```

## Schritt 4: Neue Repository verknüpfen

```bash
# Neue Repository als Origin hinzufügen
git remote add origin https://github.com/DEIN_USERNAME/the-gathering-ai.git

# Oder SSH (falls SSH-Keys konfiguriert):
# git remote add origin git@github.com:DEIN_USERNAME/the-gathering-ai.git

# Remote-Verbindung prüfen
git remote -v
```

## Schritt 5: Initial Push

```bash
# Main Branch zum neuen Repository pushen
git branch -M main
git push -u origin main

# Prüfen ob alles übertragen wurde
git log --oneline -5
```

## Schritt 6: Repository-Konfiguration

### GitHub Repository Settings:
1. **Security → Secrets and variables → Actions**
   - Falls SonarQube weiter genutzt wird: `SONAR_TOKEN` hinzufügen
   - Für AI-Integration später: `OPENAI_API_KEY` oder andere Secrets

2. **Branches → Branch protection**
   - Für main branch: "Require status checks" aktivieren
   - CI/CD Pipeline muss erfolgreich sein vor merge

3. **General → Features**
   - Issues aktivieren (für AI-Integration ToDos)
   - Projects aktivieren (optional für Kanban Board)

## Schritt 7: CI/CD Pipeline anpassen

Die `.github/workflows/ci.yml` ist bereits konfiguriert, eventuell anpassen:

```yaml
# .github/workflows/ci.yml - Zeile 70-72 für SonarQube
- name: "📊 SonarCloud Scan"
  uses: SonarSource/sonarqube-scan-action@master
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}  # <- Secret hinzufügen
```

## Schritt 8: Verifikation

```bash
# Repository-URL prüfen
git config --get remote.origin.url

# Letzten Commit remote prüfen
git ls-remote origin main

# Branch-Status
git status
```

## 🔒 Sicherheits-Checkliste

- ✅ `.env` in .gitignore (bereits vorhanden)
- ✅ `.env.example` mit Platzhaltern (soeben erstellt)
- ✅ Repository als Private markiert
- ✅ Keine echten Credentials in Commits
- ✅ SonarQube Config behalten für Code Quality

## 📝 Nächste Schritte nach Repository Setup

1. **README.md aktualisieren** mit AI-Integration Roadmap
2. **Issues erstellen** für die 3 Implementierungs-Phasen
3. **Branch-Strategie festlegen** (main + feature branches)
4. **Dependency Updates** für AI-Integration vorbereiten

## 🆘 Troubleshooting

### Problem: "Permission denied" beim Push
```bash
# SSH-Keys prüfen oder HTTPS mit Token verwenden
git remote set-url origin https://TOKEN@github.com/USERNAME/the-gathering-ai.git
```

### Problem: "Repository bereits existiert"
```bash
# Neuen Repository-Namen wählen oder bestehende löschen
# GitHub → Settings → Danger Zone → Delete Repository
```

### Problem: Git History verloren
```bash
# Lokale History ist noch da:
git log --oneline
# Bei Problemen: git push --force-with-lease origin main
```

---

**Bereit für AI-Integration nach erfolgreichem Repository Setup! 🤖**