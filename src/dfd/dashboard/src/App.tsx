import { useState } from 'react';
import {
  Masthead,
  MastheadBrand,
  MastheadContent,
  MastheadMain,
  Page,
  PageSection,
  Tab,
  Tabs,
  TabTitleText,
  Title,
  Button,
} from '@patternfly/react-core';
import { ChatIcon } from '@patternfly/react-icons';
import OverviewTab from './components/OverviewTab/OverviewTab';
import TaxonomyTab from './components/TaxonomyTab/TaxonomyTab';
import AnalysisRunsTab from './components/AnalysisRunsTab/AnalysisRunsTab';
import CostsTab from './components/CostsTab/CostsTab';
import ConversationViewer from './components/ConversationViewer/ConversationViewer';
import ChatPanel from './components/ChatPanel/ChatPanel';
import { useHashRoute } from './hooks/useHash';

const TABS = ['overview', 'taxonomy', 'analysis-runs', 'costs', 'conversations'] as const;

function App() {
  const { path, params, navigate } = useHashRoute();
  const activeTab = TABS.includes(path as typeof TABS[number]) ? path : 'overview';
  const [chatOpen, setChatOpen] = useState(false);
  const [chatRunId, setChatRunId] = useState<string | undefined>();

  const handleAskAboutRun = (pipelineRunId: string) => {
    setChatRunId(pipelineRunId);
    setChatOpen(true);
  };

  const header = (
    <Masthead>
      <MastheadMain>
        <MastheadBrand style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Title headingLevel="h1" size="xl" style={{ whiteSpace: 'nowrap' }}>
            Dumpster Fire Diving 3.0
          </Title>
        </MastheadBrand>
      </MastheadMain>
      <MastheadContent style={{ flex: 1, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.75rem' }}>
        <Button
          variant={chatOpen ? 'primary' : 'plain'}
          onClick={() => setChatOpen(!chatOpen)}
          icon={<ChatIcon />}
        >
          Chat
        </Button>
      </MastheadContent>
    </Masthead>
  );

  return (
    <Page masthead={header}>
      <PageSection>
        <Tabs
          activeKey={activeTab}
          onSelect={(_e, key) => navigate(String(key))}
          isFilled={false}
        >
          <Tab eventKey="overview" title={<TabTitleText>Overview</TabTitleText>}>
            <OverviewTab
              onAskAboutRun={handleAskAboutRun}
              hashParams={params}
              onHashParamsChange={(updates) => navigate('overview', updates)}
            />
          </Tab>
          <Tab eventKey="taxonomy" title={<TabTitleText>Taxonomy</TabTitleText>}>
            <TaxonomyTab />
          </Tab>
          <Tab eventKey="analysis-runs" title={<TabTitleText>Analysis Runs</TabTitleText>}>
            <AnalysisRunsTab />
          </Tab>
          <Tab eventKey="costs" title={<TabTitleText>Costs</TabTitleText>}>
            <CostsTab />
          </Tab>
          <Tab eventKey="conversations" title={<TabTitleText>Conversations</TabTitleText>}>
            <ConversationViewer />
          </Tab>
        </Tabs>
      </PageSection>
      <ChatPanel
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        contextRunId={chatRunId}
        onClearContext={() => setChatRunId(undefined)}
      />
    </Page>
  );
}

export default App;
