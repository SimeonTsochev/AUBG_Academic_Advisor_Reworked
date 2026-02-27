import { useState } from 'react';
import { WelcomeScreen } from './components/WelcomeScreen';
import { AcademicSetupScreen } from './components/AcademicSetupScreen';
import { MainAdvisorScreen } from './components/MainAdvisorScreen';
import { HowItWorksModal } from './components/HowItWorksModal';
import { loadDefaultCatalog, type UploadCatalogResponse } from './api';

type Screen = 'welcome' | 'setup' | 'advisor';

interface AcademicSelection {
  majors: string[];       // supports multiple majors
  minors: string[];       // supports multiple minors
  economicsIntermediateChoice: "ECO 3001" | "ECO 3002" | null;
  completedCourses: string[];
  inProgressCourses: string[];
  maxCreditsPerSemester: number;
  startTermSeason: string;
  startTermYear: number;
  waivedMat1000: boolean;
  waivedEng1000: boolean;
}

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('welcome');
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [isCatalogLoading, setIsCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [catalog, setCatalog] = useState<UploadCatalogResponse | null>(null);
  const [selection, setSelection] = useState<AcademicSelection>({
    majors: [],
    minors: [],
    economicsIntermediateChoice: null,
    completedCourses: [],
    inProgressCourses: [],
    maxCreditsPerSemester: 16,
    startTermSeason: "Fall",
    startTermYear: new Date().getFullYear(),
    waivedMat1000: false,
    waivedEng1000: false,
  });

  const handleStart = async () => {
    setCatalogError(null);
    setIsCatalogLoading(true);
    try {
      const resp = await loadDefaultCatalog();
      setCatalog(resp);
      setCurrentScreen('setup');
    } catch (e: any) {
      setCatalogError(e?.message ?? 'Failed to load catalog.');
    } finally {
      setIsCatalogLoading(false);
    }
  };

  const handleSetupComplete = (data: AcademicSelection) => {
    setSelection(data);
    setCurrentScreen('advisor');
  };

  return (
    <>
      {currentScreen === 'welcome' && (
        <WelcomeScreen
          onStart={handleStart}
          onHowItWorks={() => setShowHowItWorks(true)}
          isLoading={isCatalogLoading}
          errorMsg={catalogError ?? undefined}
        />
      )}

      {currentScreen === 'setup' && catalog && (
        <AcademicSetupScreen
          catalogYear={catalog.catalog_year ?? undefined}
          majors={catalog.majors}
          minors={catalog.minors}
          courses={catalog.courses}
          courseMeta={catalog.course_meta}
          onComplete={handleSetupComplete}
          onBack={() => setCurrentScreen('welcome')}
        />
      )}

      {currentScreen === 'advisor' && catalog && (
        <MainAdvisorScreen
          catalog={catalog}
          selection={selection}
          onBack={() => setCurrentScreen('setup')}
        />
      )}

      {showHowItWorks && (
        <HowItWorksModal onClose={() => setShowHowItWorks(false)} />
      )}
    </>
  );
}
